#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: specs.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict, cast, get_args

from sdsstools.utils import GatheringTaskGroup

from lvmopstools.clu import CluClient


if TYPE_CHECKING:
    from clu.command import Command


__all__ = [
    "spectrograph_temperature_label",
    "spectrograph_temperatures",
    "spectrograph_pressures",
    "spectrograph_mechanics",
    "spectrograph_status",
    "exposure_etr",
]


Spectrographs = Literal["sp1", "sp2", "sp3"]
Cameras = Literal["r", "b", "z"]
Sensors = Literal["ccd", "ln2"]
SpecStatus = Literal["idle", "exposing", "reading", "error", "unknown"]
SpecToStatus = dict[Spectrographs, SpecStatus]


def spectrograph_temperature_label(camera: str, sensor: str = "ccd") -> str:
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

    raise ValueError(f"Invalid camera {camera!r} or sensor {sensor!r}.")


async def spectrograph_temperatures(
    spec: Spectrographs | None = None,
    ignore_errors: bool = True,
) -> dict[str, float | None]:
    """Returns a dictionary of spectrograph temperatures.

    Parameters
    ----------
    spec
        The spectrograph to retrieve the temperatures for. If `None`, retrieves
        the temperatures for all spectrographs.
    ignore_errors
        If `True`, ignores errors when retrieving the temperatures and replaces the
        missing values with `None`. If `False`, raises an error if any of the
        temperatures cannot be retrieved.

    Returns
    -------
    dict
        A dictionary with the temperatures for each camera and sensor, e.g.,
        ``{'r1_ln2': -184.1, 'r1_ccd': -120.3, ...}``.

    """

    if spec is None:
        async with GatheringTaskGroup() as group:
            for spec in get_args(Spectrographs):
                group.create_task(
                    spectrograph_temperatures(
                        spec,
                        ignore_errors=ignore_errors,
                    )
                )

        return {
            key: value
            for task_result in group.results()
            for key, value in task_result.items()
        }

    if spec not in get_args(Spectrographs):
        raise ValueError(f"Invalid spectrograph {spec!r}.")

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    try:
        if scp_command.status.did_fail:
            raise ValueError(f"Failed retrieving status from SCP for spec {spec!r}.")

        status = scp_command.replies.get("status")
    except Exception:
        if not ignore_errors:
            raise

        status = {}

    response: dict[str, float | None] = {}

    cameras: list[Cameras] = ["r", "b", "z"]
    sensors: list[Sensors] = ["ccd", "ln2"]

    for camera in cameras:
        for sensor in sensors:
            label = spectrograph_temperature_label(camera, sensor)
            if label not in status:
                if not ignore_errors:
                    raise ValueError(f"Cannot find status label {label!r}.")
                else:
                    value = None
            else:
                value = status[label]

            response[f"{camera}{spec[-1]}_{sensor}"] = value

    return response


async def spectrograph_pressures(
    spec: Spectrographs | None = None,
    ignore_errors: bool = True,
) -> dict[str, float | None]:
    """Returns a dictionary of spectrograph pressures.

    Parameters
    ----------
    spec
        The spectrograph to retrieve the pressures for. If `None`, retrieves
        the pressures for all spectrographs.
    ignore_errors
        If `True`, ignores errors when retrieving the pressures and replaces the
        missing values with `None`. If `False`, raises an error if any of the
        pressures cannot be retrieved.

    """

    if spec is None:
        async with GatheringTaskGroup() as group:
            for spec in get_args(Spectrographs):
                group.create_task(
                    spectrograph_pressures(
                        spec,
                        ignore_errors=ignore_errors,
                    )
                )

        return {
            key: value
            for task_result in group.results()
            for key, value in task_result.items()
        }

    if spec not in get_args(Spectrographs):
        raise ValueError(f"Invalid spectrograph {spec!r}.")

    async with CluClient() as client:
        ieb_command = await client.send_command(
            f"lvmieb.{spec}",
            "transducer status",
            internal=True,
        )

    try:
        if ieb_command.status.did_fail:
            raise ValueError("Failed retrieving status from IEB.")
        pressures = ieb_command.replies.get("transducer")
    except Exception:
        if not ignore_errors:
            raise

        pressures = {}

    response: dict[str, float | None] = {}

    spec_id = spec[-1]
    keys = [f"{camera}{spec_id}_pressure" for camera in get_args(Cameras)]
    for key in keys:
        camera = key.split("_")[0]
        if key in pressures:
            response[camera] = pressures[key]
        else:
            if not ignore_errors:
                raise ValueError(f"Cannot find pressure in key {key!r}.")
            else:
                response[camera] = None

    return response


async def spectrograph_mechanics(
    spec: Spectrographs | None = None,
    ignore_errors: bool = True,
) -> dict[str, str | None]:
    """Returns a dictionary of spectrograph shutter and hartmann door status.

    Parameters
    ----------
    spec
        The spectrograph to retrieve the mechanics status for. If `None`, retrieves
        the status for all spectrographs.
    ignore_errors
        If `True`, ignores errors when retrieving the status and replaces the
        missing values with `None`. If `False`, raises an error if any of the
        status cannot be retrieved

    """

    def get_reply(cmd: Command, key: str):
        try:
            return "open" if cmd.replies.get(key)["open"] else "closed"
        except Exception:
            if not ignore_errors:
                raise ValueError(f"Cannot find key {key!r} in IEB command replies.")
            else:
                return None

    if spec is None:
        async with GatheringTaskGroup() as group:
            for spec in get_args(Spectrographs):
                group.create_task(
                    spectrograph_mechanics(
                        spec,
                        ignore_errors=ignore_errors,
                    )
                )

        return {
            key: value
            for task_result in group.results()
            for key, value in task_result.items()
        }

    if spec not in get_args(Spectrographs):
        raise ValueError(f"Invalid spectrograph {spec!r}.")

    response: dict[str, str | None] = {}

    async with CluClient() as client:
        for device in ["shutter", "hartmann"]:
            ieb_cmd = await client.send_command(
                f"lvmieb.{spec}",
                f"{device} status",
                internal=True,
            )

            if ieb_cmd.status.did_fail:
                if not ignore_errors:
                    raise ValueError(f"Failed retrieving {device } status from IEB.")

            if device == "shutter":
                key = f"{spec}_shutter"
                response[key] = get_reply(ieb_cmd, key)
            else:
                for door in ["left", "right"]:
                    key = f"{spec}_hartmann_{door}"
                    response[key] = get_reply(ieb_cmd, key)

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


class SpectrographStatusResponse(TypedDict):
    """Spectrograph status response."""

    status: SpecToStatus
    last_exposure_no: int
    etr: tuple[float, float] | tuple[None, None]


async def spectrograph_status() -> SpectrographStatusResponse:
    """Returns the status of the spectrographs."""

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

    status_dict: SpecToStatus = {}
    last_exposure_no: int = -1
    etr: tuple[float, float] | tuple[None, None] = (None, None)

    for itask, task in enumerate(group.results()):
        if itask == len(spec_names):
            etr = cast(tuple[float, float] | tuple[None, None], task)
            continue

        if task.status.did_fail:
            continue

        status = task.replies.get("status")
        controller: Spectrographs = status["controller"]
        status_names: str = status["status_names"]

        if "ERROR" in status_names:
            status_dict[controller] = "error"
        elif "IDLE" in status_names:
            status_dict[controller] = "idle"
        elif "EXPOSING" in status_names:
            status_dict[controller] = "exposing"
        elif "READING" in status_names:
            status_dict[controller] = "reading"
        else:
            status_dict[controller] = "unknown"

        last_exposure_no_key = status.get("last_exposure_no", -1)
        if last_exposure_no_key > last_exposure_no:
            last_exposure_no = cast(int, last_exposure_no_key)

    for spec in spec_names:
        if spec not in status_dict:
            status_dict[spec] = "unknown"

    response: SpectrographStatusResponse = {
        "status": status_dict,
        "last_exposure_no": last_exposure_no,
        "etr": etr,
    }

    return response
