#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-18
# @Filename: utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import os
import re
import time

from typing import Any, Coroutine, TypeVar

from nmap3 import NmapHostDiscovery

from clu import AMQPClient
from sdsstools.utils import run_in_executor

from lvmopstools import config


try:
    import netmiko
except ImportError:
    netmiko = None


__all__ = [
    "get_amqp_client",
    "get_exception_data",
    "stop_event_loop",
    "with_timeout",
    "is_notebook",
    "Trigger",
    "is_host_up",
    "power_cycle_ag_camera",
]


async def get_amqp_client(**kwargs) -> AMQPClient:  # pragma: no cover
    """Returns a CLU AMQP client."""

    amqp_client = AMQPClient(**kwargs)
    await amqp_client.start()

    return amqp_client


def get_exception_data(exception: Exception | None, traceback_frame: int = 0):
    """Returns a dictionary with information about an exception."""

    if exception is None:
        return None

    if not isinstance(exception, Exception):
        return None

    exception_data: dict[str, Any] = {}
    if exception is not None:
        filename: str | None = None
        lineno: int | None = None
        if exception.__traceback__ is not None:
            tb = exception.__traceback__
            for _ in range(traceback_frame):
                t_next = tb.tb_next
                if t_next is None:
                    break
                tb = t_next

            filename = tb.tb_frame.f_code.co_filename if tb else None
            lineno = tb.tb_lineno if tb else None

        exception_data = {
            "module": exception.__class__.__module__,
            "type": exception.__class__.__name__,
            "message": str(exception),
            "filename": filename,
            "lineno": lineno,
        }

    return exception_data


async def stop_event_loop(timeout: float | None = 5):  # pragma: no cover
    """Cancels all running tasks and stops the event loop."""

    for task in asyncio.all_tasks():
        task.cancel()

    try:
        await asyncio.wait_for(asyncio.gather(*asyncio.all_tasks()), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        asyncio.get_running_loop().stop()


def is_notebook() -> bool:
    """Returns :obj:`True` if the code is run inside a Jupyter Notebook.

    https://stackoverflow.com/questions/15411967/how-can-i-check-if-code-is-executed-in-the-ipython-notebook

    """

    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


T = TypeVar("T", bound=Any)


async def with_timeout(
    coro: asyncio.Future[T] | Coroutine[Any, Any, T],
    timeout: float | None,
    raise_on_timeout: bool = True,
) -> T | None:
    """Runs a coroutine with a timeout.

    Parameters
    ----------
    coro
        The coroutine to run.
    timeout
        The timeout in seconds.
    raise_on_timeout
        If :obj:`True`, raises a :class:`asyncio.TimeoutError` if the coroutine times
        out, otherwise returns :obj:`None`.

    Returns
    -------
    result
        The result of the coroutine.

    Raises
    ------
    asyncio.TimeoutError
        If the coroutine times out.

    """

    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        if raise_on_timeout:
            raise asyncio.TimeoutError(f"Timed out after {timeout} seconds.")


class Trigger:
    """A trigger that can be set and reset and accepts setting thresholds.

    This class is essentially just a flag that can take true/false values, but
    triggering the true value can be delayed by time or number or triggers.

    Parameters
    ----------
    n
        The number of times the instance needs to be set before it is triggered.
    delay
        The delay in seconds before the instance is triggered. This is counted from
        the first time the instance is set, and is reset if the instance is reset.
        If ``n_triggers`` is greater than 1, both conditions must be met for the
        instance to be triggered.

    """

    def __init__(self, n: int = 1, delay: float = 0):
        self.n = n
        self.delay = delay

        self._triggered = False
        self._first_trigger: float | None = None
        self._n_sets: int = 0

    def _check(self):
        """Check the trigger conditions and update the internal state."""

        now = time.time()
        if (
            self._n_sets >= self.n
            and self._first_trigger is not None
            and now - self._first_trigger >= self.delay
        ):
            self._triggered = True

    def set(self):
        """Sets the trigger."""

        if self._triggered:
            return

        self._n_sets += 1
        self._first_trigger = self._first_trigger or time.time()
        self._check()

    def reset(self):
        """Resets the trigger."""

        self._first_trigger = None
        self._n_sets = 0
        self._triggered = False

    def is_set(self):
        """Returns :obj:`True` if the trigger is set."""

        self._check()

        return self._triggered


async def is_host_up(host: str) -> bool:
    """Returns whether a host is up.

    Parameters
    ----------
    host
        The host to check.

    Returns
    -------
    is_up
        ``True`` if the host is up, ``False`` otherwise.

    """

    nmap = NmapHostDiscovery()
    result = await run_in_executor(
        nmap.nmap_no_portscan,
        host,
        args="--host-timeout=1 --max-retries=2",
    )

    if (
        host not in result
        or not isinstance(result[host], dict)
        or "state" not in result[host]
        or "state" not in result[host]["state"]
    ):
        return False

    return result[host]["state"]["state"] == "up"


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

    COMMANDS = config["devices.switch.commands"]

    lvm_switch = {
        "device_type": "netgear_prosafe",
        "host": HOST,
        "username": USERNAME,
        "password": PASSWORD,
        "secret": SECRET,  # Enable password
    }

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

    connection = netmiko.ConnectHandler(**lvm_switch)
    connection.enable()  # Enable method

    which_prompt = connection.find_prompt()  # Find prompt method
    if verbose:
        print(which_prompt)  # Print the prompt

    output = connection.send_config_set(COMMANDS[camera])
    if verbose:
        print(output)
        print("Closing connection ...")

    connection.disconnect()
