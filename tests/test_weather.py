#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-27
# @Filename: test_weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import json
import pathlib
import time

import polars
import pytest
import pytest_mock

from lvmopstools.weather import get_weather_data, is_weather_data_safe


@pytest.fixture
def mock_get_from_lco_api(mocker: pytest_mock.MockerFixture):
    data = pathlib.Path(__file__).parent / "data" / "weather_response.json"

    data = json.loads(data.read_text())
    df = polars.DataFrame(data).with_columns(
        ts=polars.col.ts.str.to_datetime(time_unit="ms", time_zone="UTC")
    )

    mocker.patch("lvmopstools.weather.get_from_lco_api", return_value=df)


@pytest.mark.parametrize(
    "start_time",
    [1732678137.5346804, "2024-11-27T03:56:10.618329", "2024-11-27 03:56:10Z"],
)
async def test_get_weather_data(mock_get_from_lco_api, start_time: str | float):
    data = await get_weather_data(start_time)

    assert isinstance(data, polars.DataFrame)
    assert data.height == 94


async def test_is_weather_data_safe(
    mock_get_from_lco_api,
    mocker: pytest_mock.MockerFixture,
):
    mocker.patch.object(time, "time", return_value=1732680854.704)

    data = await get_weather_data("2024-11-27T03:56:10.618329")

    assert is_weather_data_safe(data, "wind_speed_avg", 35)
    assert not is_weather_data_safe(data, "wind_speed_avg", 5)

    # Values are such that the max avg wind speed in the last 60 minutes is 12.11
    # and the maximum in the last 30 minutes is 10.18 mph.
    assert is_weather_data_safe(data, "wind_speed_avg", 12.5, reopen_value=10)
    assert not is_weather_data_safe(data, "wind_speed_avg", 12, reopen_value=10)
