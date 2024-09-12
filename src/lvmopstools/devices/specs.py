#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: specs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Literal, get_args

from sdsstools.utils import GatheringTaskGroup

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
        async with GatheringTaskGroup() as group:
            for spec in get_args(Spectrographs):
                group.create_task(get_spectrograph_temperatures(spec))

        return {
            key: value
            for task_result in group.results()
            for key, value in task_result.items()
        }

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    if scp_command.status.did_fail:
        raise ValueError(f"Failed retrieving status from SCP for spec {spec!r}.")

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
