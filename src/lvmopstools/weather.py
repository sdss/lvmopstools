#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-12
# @Filename: weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import datetime

import httpx
import polars

from lvmopstools import config


async def get_weather(
    start_time: float | str,
    end_time: float | str,
) -> polars.DataFrame:
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

    Returns
    -------
    weather_data
        A data frame with the weather data.

    """

    base_url: str = config["api"]

    if isinstance(start_time, (float, int)):
        start_time = (
            datetime.datetime.fromtimestamp(
                start_time,
                tz=datetime.UTC,
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    if isinstance(end_time, (float, int)):
        end_time = (
            datetime.datetime.fromtimestamp(
                end_time,
                tz=datetime.UTC,
            )
            .isoformat()
            .replace("+00:00", "Z")
        )

    async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
        response = await client.get(
            f"/weather/report?start_time={start_time}&end_time={end_time}"
        )
        response.raise_for_status()

    data_json = response.json()

    data = (
        polars.DataFrame(data_json, orient="row")
        .with_columns(ts=polars.col.ts.str.to_datetime(time_unit="ms", time_zone="UTC"))
        .rename({"ts": "time"})
    )

    return data
