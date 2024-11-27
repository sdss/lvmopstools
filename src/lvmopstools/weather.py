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

import httpx
import polars


__all__ = ["get_weather_data"]


WEATHER_URL = "http://dataservice.lco.cl/vaisala/data"


async def get_weather_data(
    start_time: str | float,
    end_time: str | float | None = None,
    station="DuPont",
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

    if station not in ["DuPont", "C40", "Magellan"]:
        raise ValueError("station must be one of 'DuPont', 'C40', or 'Magellan'.")

    if isinstance(start_time, (float, int)):
        start_time = (
            datetime.datetime.fromtimestamp(
                start_time,
                tz=datetime.UTC,
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    end_time = end_time or time.time()

    if isinstance(end_time, (float, int)):
        end_time = (
            datetime.datetime.fromtimestamp(
                end_time,
                tz=datetime.UTC,
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            WEATHER_URL,
            params={
                "start_ts": start_time,
                "end_ts": end_time,
                "station": station,
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Failed to get weather data: {response.text}")

        data = response.json()

        if "Error" in data:
            raise ValueError(f"Failed to get weather data: {data['Error']}")
        elif "results" not in data or data["results"] is None:
            raise ValueError("Failed to get weather data: no results found.")

    results = data["results"]

    df = polars.DataFrame(results)
    df = df.with_columns(
        ts=polars.col("ts").str.to_datetime(time_unit="ms"),
        station=polars.lit(station, polars.String),
    )

    # Delete rows with all null values.
    df = df.filter(~polars.all_horizontal(polars.exclude("ts", "station").is_null()))

    # Sort by timestamp
    df = df.sort("ts")

    # Convert wind speeds to mph (the LCO API returns km/h)
    df = df.with_columns(polars.selectors.starts_with("wind_") / 1.60934)

    # Calculate rolling means for average wind speed and gusts every 5m, 10m, 30m
    window_sizes = ["5m", "10m", "30m"]
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

    return df


def is_measurament_safe(
    data: polars.DataFrame,
    measurement: str,
    threshold: float,
    window: int = 30,
    rolling_average_window: int = 30,
    reopen_value: float | None = None,
):
    """Determines whether an alert should be raised for a given measurement.

    An alert will be issued if the rolling average value of the ``measurement``
    (a column in ``data``) over the last ``window`` seconds is above the
    ``threshold``. Once the alert has been raised  the value of the ``measurement``
    must fall below the ``reopen_value`` to close the alert (defaults to the same
    ``threshold`` value) in a rolling.

    ``window`` and ``rolling_average_window`` are in minutes.

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
    data = data.with_columns(
        average=polars.col(measurement).rolling_mean_by(
            by="ts",
            window_size=f"{rolling_average_window}m",
        )
    )

    # Get data from the last window`.
    now = time.time()
    data_window = data.filter(polars.col.ts.dt.timestamp("ms") > (now - window * 60))

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
        polars.col.ts.dt.timestamp("ms") > (now - 2 * window * 60),
        polars.col.ts.dt.timestamp("ms") < (now - window * 60),
    )
    if (prev_window["average"] >= threshold).any():
        return (data_window["average"] < reopen_value).all()

    return True
