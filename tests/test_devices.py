#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: test_devices.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncudp

from drift import Drift

from lvmopstools import config
from lvmopstools.devices.ion import ALL, read_ion_pumps, toggle_ion_pump
from lvmopstools.devices.thermistors import read_thermistors


if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class MockSocket:
    def __init__(self, next_recv: bytes = b""):
        self.next_recv = next_recv

    async def sendto(self, data):
        pass

    async def recvfrom(self):
        return self.next_recv, None

    async def close(self):
        pass


async def test_read_thermistors(mocker: MockerFixture):
    """Tests read_thermistors."""

    mocker.patch.object(
        asyncudp,
        "create_socket",
        return_value=MockSocket(b"!01000180\r"),
    )

    thermistors = await read_thermistors()

    for thermistor in config["devices.thermistors"]["channels"]:
        if thermistor in ["supply", "r1"]:
            assert thermistors[thermistor]
        else:
            assert not thermistors[thermistor]


async def test_check_config():
    """Checks that the test configuration file is loaded correctly."""

    assert len(config["devices.ion"]) == 1
    assert config["devices.ion"][0]["host"] == "127.0.0.1"
    assert config["devices.ion"][0]["port"] == 5020


async def test_read_ion_pumps(ion_pump_server):
    """Tests ``read_ion_pumps``."""

    values = await read_ion_pumps()

    assert values["b2"]["pressure"] is not None
    assert values["b2"]["pressure"] > 1e-6
    assert values["b2"]["on"]

    assert values["z2"]["pressure"] is None
    assert values["z2"]["on"] is False

    values_b2 = await read_ion_pumps(cameras=["b2"])
    assert len(values_b2) == 1


async def test_toggle_ion_pump(ion_pump_server):
    """Tests ``toggle_ion_pump``."""

    drift = Drift(config["devices.ion"][0]["host"], config["devices.ion"][0]["port"])

    b2_config = config["devices.ion"][0]["cameras"]["b2"]
    on_off_address = b2_config["on_off_address"]

    async with drift:
        register_z2 = await drift.client.read_holding_registers(on_off_address, 1)
        assert register_z2.registers[0] == 0

    await toggle_ion_pump("b2", True)

    async with drift:
        register_z2 = await drift.client.read_holding_registers(0, 50)
        assert sum([reg > 0 for reg in register_z2.registers]) == 1


async def test_toggle_ion_pump_all(ion_pump_server):
    """Tests turning on all the ion pumps."""

    drift = Drift(config["devices.ion"][0]["host"], config["devices.ion"][0]["port"])

    await toggle_ion_pump(ALL, True)

    async with drift:
        register_z2 = await drift.client.read_holding_registers(0, 50)
        assert sum([reg > 0 for reg in register_z2.registers]) == 3
