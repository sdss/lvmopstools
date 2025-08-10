#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2025-08-10
# @Filename: ags.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from lvmopstools import config
from lvmopstools.clu import send_clu_command
from lvmopstools.devices.switch import power_cycle_interface


async def power_cycle_ag_camera_nps(
    camera: str,
    delay: float = 3,
    verbose: bool = False,
):
    """Power cycles the NPS for the given auto-guide camera.

    Parameters
    ----------
    camera
        The name of the camera to power cycle.
    delay
        The delay in seconds before power cycling the camera.
    verbose
        If True, prints the commands that are being run.

    """

    ags_config = config["devices.agcams.power"][camera]
    actor = ags_config["actor"]
    outlet = ags_config["outlet"]

    if verbose:
        print(f"Power cycling camera {camera!r} via NPS...")

    cmd = await send_clu_command(f"{actor} cycle --delay {delay} {outlet}", raw=True)
    if cmd.status.did_fail:
        raise RuntimeError(f"Failed to power cycle camera {camera!r} via NPS.")

    if verbose:
        print(f"Power cycling of {camera!r} complete.")


async def power_cycle_ag_camera(camera: str, verbose: bool = False):
    """Power cycles an AG camera either by resetting PoE or toggling the NPS.

    Parameters
    ----------
    camera
        The name of the camera to power cycle.
    verbose
        If True, prints the commands that are being run.

    """

    if not isinstance(camera, str):
        camera = str(camera)

    ags_config = config["devices.agcams.power"]

    for cam_config_name in ags_config:
        aliases = ags_config[cam_config_name]["aliases"] or []
        if camera.lower() == cam_config_name.lower() or camera in aliases:
            camera = cam_config_name
            break
    else:
        raise ValueError(f"Invalid camera name {camera}")

    ag_camera_config = ags_config[camera]

    if ag_camera_config["mode"] == "poe":
        interface = ag_camera_config["interface"]
        power_cycle_interface(interface, verbose=verbose)
    elif ag_camera_config["mode"] == "nps":
        await power_cycle_ag_camera_nps(camera, verbose=verbose)
