#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: specs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any, Literal, get_args

from sdsstools.utils import GatheringTaskGroup

from lvmopstools.clu import CluClient


__all__ = [
    "spectrograph_temperature_label",
    "spectrograph_temperatures",
    "spectrograph_pressures",
    "spectrograph_mechanics",
    "exposure_etr",
    "spectrogaph_status",
]


Spectrographs = Literal["sp1", "sp2", "sp3"]
Cameras = Literal["r", "b", "z"]
Sensors = Literal["ccd", "ln2"]
SpecStatus = Literal["idle", "exposing", "reading", "error", "unknown"]
SpecToStatus = dict[Spectrographs, SpecStatus]


def spectrograph_temperature_label(camera: str, sensor: str = "ccd"):
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


async def spectrograph_temperatures(spec: Spectrographs | None = None):
    """Returns a dictionary of spectrograph temperatures."""

    if spec is None:
        async with GatheringTaskGroup() as group:
            for spec in get_args(Spectrographs):
                group.create_task(spectrograph_temperatures(spec))

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
            label = spectrograph_temperature_label(camera, sensor)
            if label not in status:
                raise ValueError(f"Cannot find status label {label!r}.")
            response[f"{camera}{spec[-1]}_{sensor}"] = status[label]

    return response


async def spectrograph_pressures(spec: Spectrographs):
    """Returns a dictionary of spectrograph pressures."""

    async with CluClient() as client:
        ieb_command = await client.send_command(
            f"lvmieb.{spec}",
            "transducer status",
            internal=True,
        )

    if ieb_command.status.did_fail:
        raise ValueError("Failed retrieving status from IEB.")

    pressures = ieb_command.replies.get("transducer")

    response: dict[str, float] = {}
    for key in pressures:
        if "pressure" in key:
            response[key] = pressures[key]

    return response


async def spectrograph_mechanics(spec: Spectrographs):
    """Returns a dictionary of spectrograph shutter and hartmann door status."""

    response: dict[str, str] = {}

    async with CluClient() as client:
        for device in ["shutter", "hartmann"]:
            ieb_cmd = await client.send_command(
                f"lvmieb.{spec}",
                f"{device} status",
                internal=True,
            )

            if ieb_cmd.status.did_fail:
                raise ValueError(f"Failed retrieving {device } status from IEB.")

            if device == "shutter":
                key = f"{spec}_shutter"
                response[key] = "open" if ieb_cmd.replies.get(key)["open"] else "closed"
            else:
                for door in ["left", "right"]:
                    key = f"{spec}_hartmann_{door}"
                    reply = ieb_cmd.replies.get(key)
                    response[key] = "open" if reply["open"] else "closed"

    return response


async def exposure_etr() -> tuple[float | None, float | None]:
    """Returns the ETR for the exposure, including readout."""

    spec_names = get_args(Spectrographs)

    async with CluClient() as client:
        async with GatheringTaskGroup() as group:
            for spec in spec_names:
                group.create_task(
                    client.send_command(
                        f"lvmscp.{spec}",
                        "get-etr",
                        internal=True,
                    )
                )

    etrs: list[float] = []
    total_times: list[float] = []
    for task in group.results():
        if task.status.did_fail:
            continue

        etr = task.replies.get("etr")
        if all(etr):
            etrs.append(etr[0])
            total_times.append(etr[1])

    if len(etrs) == 0 or len(total_times) == 0:
        return None, None

    return max(etrs), max(total_times)


async def spectrogaph_status() -> dict[str, Any]:
    """Returns the status of the spectrograph (integrating, reading, etc.)"""

    spec_names = get_args(Spectrographs)

    async with CluClient() as client:
        async with GatheringTaskGroup() as group:
            for spec in spec_names:
                group.create_task(
                    client.send_command(
                        f"lvmscp.{spec}",
                        "status -s",
                        internal=True,
                    )
                )
            group.create_task(exposure_etr())

    result: SpecToStatus = {}
    last_exposure_no: int = -1
    etr: tuple[float | None, float | None] = (None, None)

    for itask, task in enumerate(group.results()):
        if itask == len(spec_names):
            etr = task
            continue

        if task.status.did_fail:
            continue

        status = task.replies.get("status")
        controller: Spectrographs = status["controller"]
        status_names: str = status["status_names"]

        if "ERROR" in status_names:
            result[controller] = "error"
        elif "IDLE" in status_names:
            result[controller] = "idle"
        elif "EXPOSING" in status_names:
            result[controller] = "exposing"
        elif "READING" in status_names:
            result[controller] = "reading"
        else:
            result[controller] = "unknown"

        last_exposure_no_key = status.get("last_exposure_no", -1)
        if last_exposure_no_key > last_exposure_no:
            last_exposure_no = last_exposure_no_key

    for spec in spec_names:
        if spec not in result:
            result[spec] = "unknown"

    return {"status": result, "last_exposure_no": last_exposure_no, "etr": etr}
