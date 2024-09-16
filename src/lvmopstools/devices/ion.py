#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-11
# @Filename: ion.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import warnings

from typing import TypedDict

from drift import Drift
from drift.convert import data_to_float32

from lvmopstools import config
from lvmopstools.retrier import Retrier


__all__ = ["read_ion_pumps", "toggle_ion_pump", "convert_pressure", "ALL"]


#: Flag to toggle all ion pumps.
ALL = "all"


def convert_pressure(volts: float):
    """Converts differential voltage to pressure in Torr."""

    # The calibration is a linear fit of the form y = mx + b
    m = 2.04545
    b = -6.86373

    log10_pp0 = m * volts + b  # log10(PPa), pressure in Pascal

    torr = 10**log10_pp0 * 0.00750062

    return torr


class IonPumpDict(TypedDict):
    """Ion pump dictionary."""

    pressure: float | None
    on: bool | None


@Retrier(max_attempts=3, delay=1)
async def _read_one_ion_controller(ion_config: dict) -> dict[str, IonPumpDict]:
    """Reads the signal and on/off status from an ion controller."""

    results: dict[str, IonPumpDict] = {}

    drift = Drift(ion_config["host"], ion_config.get("port", 502), timeout=1)

    async with drift:
        for camera, camera_config in ion_config["cameras"].items():
            signal_address = camera_config["signal_address"]
            # on_off_address = camera_config["on_off_address"]

            signal = await drift.client.read_input_registers(signal_address, 2)
            # onoff = await drift.client.read_input_registers(on_off_address, 1)

            diff_volt = data_to_float32(tuple(signal.registers))
            pressure = convert_pressure(diff_volt)

            # onoff_status = bool(onoff.registers[0])
            onoff_status = pressure > 1e-8

            # No point in reporting a bogus pressure.
            if pressure < 1e-8:
                pressure = None

            results[camera] = {"pressure": pressure, "on": onoff_status}

    return results


async def read_ion_pumps(cameras: list[str] | None = None) -> dict[str, IonPumpDict]:
    """Reads the signal and on/off status from an ion pump.

    Parameters
    ----------
    cameras
        A list of cameras to read. If `None`, reads all cameras.

    """

    ion_config: list[dict] = config["devices.ion"]

    results: dict[str, IonPumpDict] = {}
    tasks: list[asyncio.Task] = []

    for ion_controller in ion_config:
        controller_cameras = ion_controller["cameras"]
        if cameras is not None:
            # Skip reading this controller if none of the cameras are in the list.
            if len(set(cameras) & set(controller_cameras)) == 0:
                continue

        for camera in controller_cameras:
            results[camera] = {"pressure": None, "on": None}

        tasks.append(asyncio.create_task(_read_one_ion_controller(ion_controller)))

    await asyncio.gather(*tasks, return_exceptions=True)

    for task in tasks:
        if task.exception():
            warnings.warn(f"Error reading ion pump: {task.exception()}")
            continue

        for camera, item in task.result().items():
            results[camera] = item

    if cameras is not None:
        results = {camera: results[camera] for camera in cameras if camera in results}

    if cameras is not None and set(results.keys()) != set(cameras):
        warnings.warn("Not all cameras were found in the configuration.")

    return results


@Retrier(max_attempts=3, delay=1)
async def toggle_ion_pump(camera: str, on: bool):
    """Turns the ion pump on or off.

    Parameters
    ----------
    camera
        The camera for which to toggle the ion pump. Can also be :obj:`.ALL` to
        toggle all ion pumps.
    on
        If `True`, turns the pump on. If `False`, turns the pump off. If `None`,
        toggles the pump current status.

    """

    ion_config: list[dict] = config["devices.ion"]

    if camera == ALL:
        cameras = [camera for ic in ion_config for camera in ic["cameras"]]
        for camera in cameras:
            await toggle_ion_pump(camera, on)
        return

    host: str | None = None
    port: int | None = None
    on_off_address: int | None = None

    for ic in ion_config:
        if camera in ic["cameras"]:
            host = ic["host"]
            port = ic.get("port", 502)
            on_off_address = ic["cameras"][camera]["on_off_address"]
            break

    if host is None or port is None or on_off_address is None:
        raise ValueError(f"Camera {camera!r} not found in the configuration.")

    drift = Drift(host, port)

    async with drift:
        value = 2**16 - 1 if on else 0
        await drift.client.write_register(on_off_address, value)
