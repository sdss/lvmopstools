#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2025-03-20
# @Filename: switch.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import warnings

from lvmopstools import config


try:
    import netmiko
except ImportError:
    netmiko = None


__all__ = ["power_cycle_interface", "get_ag_poe_port_info"]


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


def power_cycle_interface(interface: str, verbose: bool = False):
    """Power cycles the PoE for a switch interface.

    The environment variales ``LVM_SWITCH_HOST``, ``LVM_SWITCH_USERNAME``,
    ``LVM_SWITCH_PASSWORD``, and ``LVM_SWITCH_SECRET`` must be set when
    calling this function.

    Parameters
    ----------
    interface
        The switch interface to power cycle, e.g., ``"2/0/6"``.
    verbose
        If ``True``, prints the commands that are being run.

    """

    connection = _get_connection()

    output = connection.send_config_set([f"interface {interface}", "poe reset"])
    if verbose:
        print(output)
        print("Closing connection ...")

    connection.disconnect()


def get_ag_poe_port_info(camera: str | None = None) -> dict[str, str]:
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

    agcams_config = config["devices.agcams.power"]

    results: dict[str, str] = {}
    for cam_config_name, cam_config in agcams_config.items():
        if camera is None or camera.lower() == cam_config_name.lower():
            interface = cam_config["interface"]
            if interface is None:
                warnings.warn(f"Interface for camera {cam_config_name} is not set.")
                continue

            data = connection.send_command(f"show poe port info {interface}")
            assert isinstance(data, str)

            results[cam_config_name] = data

    if camera is not None and len(results) == 0:
        raise ValueError(f"No PoE port information found for camera {camera}.")

    connection.disconnect()

    return results
