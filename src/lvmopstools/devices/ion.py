#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-11
# @Filename: ion.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from drift import Drift
from drift.convert import data_to_float32
from sdsstools import GatheringTaskGroup

from lvmopstools import config


def convert_pressure(volts: float):
    """Converts differential voltage to pressure in Torr."""

    # The calibration is a linear fit of the form y = mx + b
    m = 2.04545
    b = -6.86373

    log10_pp0 = m * volts + b  # log10(PPa), pressure in Pascal

    torr = 10**log10_pp0 * 0.00750062

    return torr


async def _read_one_ion_controller(ion_config: dict):
    """Reads the signal and on/off status from an ion controller."""

    results: dict[str, dict] = {}

    drift = Drift(ion_config["host"], ion_config.get("port", 502))

    async with drift:
        for camera, camera_config in ion_config["cameras"].items():
            signal_address = camera_config["signal_address"]
            # onoff_address = camera_config["onoff_address"]

            signal = await drift.client.read_input_registers(signal_address, 2)
            # onoff = await drift.client.read_input_registers(onoff_address, 1)

            diff_volt = data_to_float32(tuple(signal.registers))
            pressure = convert_pressure(diff_volt)

            # onoff_status = bool(onoff.registers[0])
            onoff_status = pressure > 1e-8

            results[camera] = {"pressure": pressure, "on": onoff_status}

    return results


async def read_ion_pumps():
    """Reads the signal and on/off status from an ion pump."""

    ion_config: list[dict] = config["devices.ion"]

    async with GatheringTaskGroup() as group:
        for ion_controller in ion_config:
            group.create_task(_read_one_ion_controller(ion_controller))

    results = {camera: item[camera] for item in group.results() for camera in item}

    return results


async def toggle_ion_pump(camera: str, on: bool):
    """Turns the ion pump on or off.

    Parameters
    ----------
    camera
        The camera for which to toggle the ion pump.
    on
        If `True`, turns the pump on. If `False`, turns the pump off. If `None`,
        toggles the pump current status.

    """

    ion_config: list[dict] = config["devices.ion"]

    host: str | None = None
    port: int | None = None
    on_off_address: int | None = None

    for ic in ion_config:
        if camera in ic["cameras"]:
            host = ic["host"]
            port = ic.get("port", 502)
            on_off_address = ic["cameras"][camera]["onoff_address"]
            break

    if host is None or port is None or on_off_address is None:
        raise ValueError(f"Camera {camera!r} not found in the configuration.")

    drift = Drift(host, port)

    async with drift:
        value = 2**16 - 1 if on else 0
        await drift.client.write_register(on_off_address, value)
