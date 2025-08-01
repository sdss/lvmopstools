#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-26
# @Filename: weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import datetime
import time
import warnings

from typing import Literal

import httpx
import polars


__all__ = ["get_weather_data", "is_weather_data_safe"]


WEATHER_URL = "http://env-api.lco.cl/metrics/weather"

WEATHER_SCHEMA = polars.Schema(
    {
        "ts": polars.String,
        "temperature": polars.Float32,
        "air_pressure": polars.Float32,
        "wind_dir_avg": polars.Float32,
        "wind_dir_max": polars.Float32,
        "wind_dir_min": polars.Float32,
        "rain_intensity": polars.Float32,
        "wind_speed_avg": polars.Float32,
        "wind_speed_max": polars.Float32,
        "wind_speed_min": polars.Float32,
        "relative_humidity": polars.Float32,
    }
)


def format_time(time: str | float) -> str:
    """Formats a time string for the LCO weather API format"""

    if isinstance(time, (float, int)):
        time = (
            datetime.datetime.fromtimestamp(
                time,
                tz=datetime.timezone.utc,
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "")
        )

    if "." in time:
        time = time.split(".")[0]

    return time


async def get_from_lco_api(
    start_time: str,
    end_time: str,
    station: str,
):  # pragma: no cover
    """Queries the LCO API for weather data."""

    start_time_dt = datetime.datetime.strptime(
        start_time,
        "%Y-%m-%dT%H:%M:%S",
    )
    end_time_dt = datetime.datetime.strptime(
        end_time,
        "%Y-%m-%dT%H:%M:%S",
    )

    data_chunks: list[polars.DataFrame] = []

    async with httpx.AsyncClient() as client:
        dt0 = start_time_dt

        # The API will only return one hour of data so we loop over it and concatenate.
        while True:
            # Use chunks of 30 minutes to be completely sure the API will return
            # the data for that interval.
            dt1 = dt0 + datetime.timedelta(hours=0.5)

            response = await client.get(
                WEATHER_URL,
                params={
                    "start_ts": dt0.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end_ts": dt1.strftime("%Y-%m-%dT%H:%M:%S"),
                    "source": station.lower(),
                },
            )

            if response.status_code != 200:
                raise ValueError(f"Failed to get weather data: {response.text}")

            data = response.json()

            if "Error" in data:
                raise ValueError(f"Failed to get weather data: {data['Error']}")
            elif "results" not in data or data["results"] is None:
                raise ValueError("Failed to get weather data: no results found.")
            elif len(data["results"]) == 0:
                data_df = polars.DataFrame([], schema=WEATHER_SCHEMA)
            else:
                data_df = polars.DataFrame(data["results"], schema=WEATHER_SCHEMA)

            data_df = data_df.with_columns(
                ts=polars.col.ts.str.to_datetime(
                    time_unit="ms",
                    time_zone="UTC",
                )
            )

            data_chunks.append(data_df)

            if dt1 >= end_time_dt:
                break

            # Increase the time window by a bit less than 30 minutes to ensure that
            # we don't lose any data points.
            dt0 = dt0 + datetime.timedelta(hours=0.45)

    data = polars.concat(data_chunks).filter(
        polars.col.ts.dt.replace_time_zone(None) >= start_time_dt,
        polars.col.ts.dt.replace_time_zone(None) <= end_time_dt,
    )

    # Temperature is in Fahrenheit, convert to Celsius.
    data = data.with_columns(temperature=(polars.col.temperature - 32) * 5 / 9)

    return data


async def get_weather_data(
    start_time: str | float,
    end_time: str | float | None = None,
    station: Literal["dupont", "swope", "magellan"] = "dupont",
):
    """Returns a data frame with weather data from the du Pont station.

    .. warning::
        This function can only be run from inside the LVM network since it uses the
        LVM API which is not publicly accessible.

    Parameters
    ----------
    start_time
        The start time of the query. Can be a UNIX timestamp or an ISO datetime string.
    end_time
        The end time of the query. Can be a UNIX timestamp or an ISO datetime string.
        Defaults to the current time.
    station
        The station to query. Must be one of 'DuPont', 'C40', or 'Magellan'.

    Returns
    -------
    weather_data
        A data frame with the weather data.

    """

    if station not in ["dupont", "swope", "magellan"]:
        raise ValueError("station must be one of 'dupont', 'swope', or 'magellan'.")

    start_time = format_time(start_time)
    end_time = format_time(end_time or time.time())

    df = await get_from_lco_api(start_time, end_time, station)
    df = df.with_columns(station=polars.lit(station, polars.String))

    # Delete rows with all null values.
    df = df.filter(~polars.all_horizontal(polars.exclude("ts", "station").is_null()))

    # Sort by timestamp and keep only unique timestamps.
    df = df.sort("ts").unique("ts")

    # Calculate rolling means for average wind speed and gusts every 5m, 10m, 30m
    window_sizes = ["5m", "10m", "30m"]
    wind_cols = df.select(["wind_speed_avg", "wind_speed_max", "wind_dir_avg"])

    if wind_cols.null_count().sum_horizontal().item() > 0:
        # Sometimes we don't have wind data available, especially
        # if the anemometer has frozen.
        for ws in window_sizes:
            df = df.with_columns(
                **{
                    f"wind_speed_avg_{ws}": polars.lit(None, polars.Float32),
                    f"wind_gust_{ws}": polars.lit(None, polars.Float32),
                    f"wind_dir_avg_{ws}": polars.lit(None, polars.Float32),
                }
            )
    else:
        df = df.with_columns(
            **{
                f"wind_speed_avg_{ws}": polars.col.wind_speed_avg.rolling_mean_by(
                    by="ts",
                    window_size=ws,
                )
                for ws in window_sizes
            },
            **{
                f"wind_gust_{ws}": polars.col.wind_speed_max.rolling_max_by(
                    by="ts",
                    window_size=ws,
                )
                for ws in window_sizes
            },
            **{
                f"wind_dir_avg_{ws}": polars.col.wind_dir_avg.rolling_mean_by(
                    by="ts",
                    window_size=ws,
                )
                for ws in window_sizes
            },
        )

    # Add simple dew point.
    df = df.with_columns(
        dew_point=polars.col.temperature
        - ((100 - polars.col.relative_humidity) / 5.0).round(2)
    )

    # Change float precision to f32
    df = df.with_columns(polars.selectors.float().cast(polars.Float32))

    return df


def is_weather_data_safe(
    data: polars.DataFrame,
    measurement: str,
    threshold: float,
    now: float | datetime.datetime | None = None,
    window: int = 30,
    rolling_average_window: int = 10,
    reopen_value: float | None = None,
):
    """Determines whether an alert should be raised for a given weather measurement.

    An alert will be issued if the rolling average value of the ``measurement``
    (a column in ``data``) over the last ``window`` minutes is above the
    ``threshold``. Once the alert has been raised  the value of the ``measurement``
    must fall below the ``reopen_value`` to close the alert (defaults to the same
    ``threshold`` value) in a rolling.

    If ``now`` is not provie the current time is used as the reference point.

    ``window`` and ``rolling_average_window`` are in minutes.

    Examples
    --------
    >>> is_weather_data_safe(data, "wind_speed_avg", 35)
    True

    Returns
    -------
    result
        A boolean indicating whether the measurement is safe. `True` means the
        measurement is in a valid, safe range.

    """

    if measurement not in data.columns:
        raise ValueError(f"Measurement {measurement} not found in data.")

    reopen_value = reopen_value or threshold

    data = data.select(polars.col.ts, polars.col(measurement))
    data = data.filter(~polars.all_horizontal(polars.exclude("ts").is_null()))
    data = data.sort("ts")
    data = data.with_columns(
        timestamp=polars.col.ts.dt.timestamp("ms") / 1000,
        average=polars.col(measurement).rolling_mean_by(
            by="ts",
            window_size=f"{rolling_average_window}m",
        ),
    )

    # Get data from the last window`.
    if now is None:
        now = time.time()
    elif isinstance(now, datetime.datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=datetime.timezone.utc)
        now = now.timestamp()

    data_window = data.filter(polars.col.timestamp > (now - window * 60))

    if data_window.height == 0:
        warnings.warn("No data available for the specified measurement.", UserWarning)
        return False

    # If any of the values in the last "window" is above the threshold, it's unsafe.
    if (data_window["average"] >= threshold).any():
        return False

    # If all the values in the last "window" are below the reopen threshold, it's safe.
    if (data_window["average"] < reopen_value).all():
        return True

    # The last case is if the values in the last "window" are between the reopen and
    # the threshold values. We want to avoid the returned value flipping from true
    # to false in a quick manner. We check the previous "window" minutes to see if
    # the alert was raised at any point. If so, we require the current window to
    # be below the reopen value. Otherwise, we consider it's safe.

    prev_window = data.filter(
        polars.col.timestamp > (now - 2 * window * 60),
        polars.col.timestamp < (now - window * 60),
    )
    if (prev_window["average"] >= threshold).any():
        return False

    return True
