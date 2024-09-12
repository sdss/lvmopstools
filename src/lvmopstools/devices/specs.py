#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: specs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from typing import Literal, get_args

from lvmopstools.clu import CluClient


__all__ = ["get_spectrograph_temperature_label", "get_spectrograph_temperatures"]


Spectrographs = Literal["sp1", "sp2", "sp3"]
Cameras = Literal["r", "b", "z"]
Sensors = Literal["ccd", "ln2"]


def get_spectrograph_temperature_label(camera: str, sensor: str = "ccd"):
    """Returns the archon label associated with a temperature sensor."""

    if sensor == "ccd":
        if camera == "r":
            return "mod2/tempa"
        elif camera == "b":
            return "mod12/tempc"
        elif camera == "z":
            return "mod12/tempa"

    else:
        if camera == "r":
            return "mod2/tempb"
        elif camera == "b":
            return "mod2/tempc"
        elif camera == "z":
            return "mod12/tempb"


async def get_spectrograph_temperatures(spec: Spectrographs | None = None):
    """Returns a dictionary of spectrograph temperatures."""

    if spec is None:
        tasks: list[asyncio.Task] = []
        for spec in get_args(Spectrographs):
            tasks.append(asyncio.create_task(get_spectrograph_temperatures(spec)))

        task_results = await asyncio.gather(*tasks)
        return {
            key: value
            for task_result in task_results
            for key, value in task_result.items()
        }

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    if scp_command.status.did_fail:
        raise ValueError("Failed retrieving status from SCP.")

    status = scp_command.replies.get("status")

    response: dict[str, float] = {}

    cameras: list[Cameras] = ["r", "b", "z"]
    sensors: list[Sensors] = ["ccd", "ln2"]

    for camera in cameras:
        for sensor in sensors:
            label = get_spectrograph_temperature_label(camera, sensor)
            if label not in status:
                raise ValueError(f"Cannot find status label {label!r}.")
            response[f"{camera}{spec[-1]}_{sensor}"] = status[label]

    return response
