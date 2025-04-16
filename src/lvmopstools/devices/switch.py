#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2025-03-20
# @Filename: switch.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import re

from lvmopstools import config


try:
    import netmiko
except ImportError:
    netmiko = None


__all__ = ["power_cycle_ag_camera", "get_poe_port_info"]


def _get_connection(enable: bool = True):
    """Gets a connection to the switch."""

    if not netmiko:
        raise ImportError("netmiko is required to power cycle the switch port.")

    HOST: str = os.getenv("LVM_SWITCH_HOST", config["devices.switch.host"])
    USERNAME: str = os.getenv("LVM_SWITCH_USERNAME", config["devices.switch.username"])
    PASSWORD: str | None = os.getenv("LVM_SWITCH_PASSWORD")
    SECRET: str | None = os.getenv("LVM_SWITCH_SECRET")

    if not PASSWORD:
        raise ValueError("$LVM_SWITCH_PASSWORD has not been set.")
    if not SECRET:
        raise ValueError("$LVM_SWITCH_SECRET has not been set.")

    lvm_switch = {
        "device_type": "netgear_prosafe",
        "host": HOST,
        "username": USERNAME,
        "password": PASSWORD,
        "secret": SECRET,  # Enable password
    }

    connection = netmiko.ConnectHandler(**lvm_switch)

    if enable:
        connection.enable()  # Enable method

    return connection


def power_cycle_ag_camera(camera: str, verbose: bool = False):
    """Power cycles the switch port for the given auto-guide camera.

    The environment variales ``LVM_SWITCH_HOST``, ``LVM_SWITCH_USERNAME``,
    ``LVM_SWITCH_PASSWORD``, and ``LVM_SWITCH_SECRET`` must be set when
    calling this function.

    Parameters
    ----------
    camera
        The name of the camera to power cycle. Valid values are ``'CAM-111'``,
        ``'111'``, ``'sci-east'`` (where 111 is the last octet of the IP address).
    verbose
        If ``True``, prints the commands that are being run.

    """

    if not isinstance(camera, str):
        camera = str(camera)

    if re.match(r"^\d+$", camera):
        camera = f"CAM-{camera}"
    elif re.match(r"^CAM-\d+$", camera, re.IGNORECASE):
        camera = camera.upper()
    elif re.match(r"^(sci|spec|skye|skyw)-(east|west)$", camera, re.IGNORECASE):
        camera = config["devices.switch.camera_to_ip"][camera.lower()]
    else:
        raise ValueError(f"invalid camera name {camera}")

    connection = _get_connection()

    cam_interface = config["devices.switch.camera_to_interface"][camera]

    output = connection.send_config_set([f"interface {cam_interface}", "poe reset"])
    if verbose:
        print(output)
        print("Closing connection ...")

    connection.disconnect()


def get_poe_port_info(camera: str | None = None) -> dict[str, str]:
    """Returns the PoE port information for a given camera.

    Parameters
    ----------
    camera
        The name of the camera. If not provided, returns the information
        for all cameras.

    Returns
    -------
    dict
        A dictionary with the PoE port information for the camera.

    """

    connection = _get_connection()

    cam_interfaces = config["devices.switch.camera_to_interface"]

    results: dict[str, str] = {}
    cams = [camera] if camera else config["devices.switch.camera_to_ip"].keys()

    for cam in cams:
        interface = cam_interfaces[config["devices.switch.camera_to_ip"][cam]]

        data = connection.send_command(f"show poe port info {interface}")
        assert isinstance(data, str)

        results[cam] = data

    connection.disconnect()

    return results
