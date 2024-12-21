#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-27
# @Filename: test_schedule.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import polars
import pytest_mock
from astropy.time import Time

from lvmopstools.ephemeris import create_schedule, get_ephemeris_summary, is_sun_up


def test_create_schedule():
    data = create_schedule(59948, 59957)

    assert isinstance(data, polars.DataFrame)
    assert data.height == 10


def test_get_ephemeris_summary():
    summary = get_ephemeris_summary(59957)

    assert isinstance(summary, dict)
    assert summary["from_file"]
    assert summary["SJD"] == 59957


def test_get_ephemeris_summary_not_in_file():
    summary = get_ephemeris_summary(59900)

    assert isinstance(summary, dict)
    assert not summary["from_file"]
    assert summary["sunset"] is not None


def test_is_sun_up(mocker: pytest_mock.MockFixture):
    mocker.patch("lvmopstools.ephemeris.get_sjd", return_value=60666)
    mocker.patch(
        "lvmopstools.ephemeris.Time.now",
        return_value=Time("2024-12-21 23:51:18.464285", format="iso", scale="utc"),
    )

    assert is_sun_up() is True
    assert is_sun_up(include_twilight=True) is False
