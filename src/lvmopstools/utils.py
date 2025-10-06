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
import subprocess
import time
import warnings
from functools import wraps

from typing import Any, Coroutine, TypeVar

import nmap3

from clu import AMQPClient
from sdsstools.utils import run_in_executor


try:
    import netmiko
except ImportError:
    netmiko = None


__all__ = [
    "get_amqp_client",
    "get_exception_data",
    "stop_event_loop",
    "with_timeout",
    "timeout",
    "is_notebook",
    "Trigger",
    "is_host_up",
    "is_root",
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


def timeout(timeout: float, raise_on_timeout: bool = True):
    """Decorator that wraps an async function with :obj:`asyncio.wait_for`.

    Parameters
    ----------
    timeout
        The timeout in seconds.
    raise_on_timeout
        If :obj:`True`, raises a :class:`asyncio.TimeoutError` if the coroutine times
        out, otherwise returns :obj:`None`.

    Example
    -------
    @timeout(5)
    async def work(): ...

    @timeout(5, raise_on_timeout=False)
    async def maybe(): ...

    """

    def decorator(func):
        if not asyncio.iscoroutinefunction(func):
            raise TypeError("timeout decorator can only be applied to async functions.")

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout)
            except asyncio.TimeoutError:
                if raise_on_timeout:
                    raise asyncio.TimeoutError(
                        f"{func.__name__} timed out after {timeout} seconds."
                    )
                return None

        return wrapper

    return decorator


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


def is_root():
    """Returns whether the user is root. This may not work in all systems."""

    return os.geteuid() == 0


async def ping_host(host: str):
    """Pings a host."""

    cmd = await asyncio.create_subprocess_exec(
        *["ping", "-c", "1", "-W", "5", host],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return_code = await cmd.wait()
    return return_code == 0


async def is_host_up(host: str, fallback_to_ping: bool = True) -> bool:
    """Returns whether a host is up.

    Parameters
    ----------
    host
        The host to check.
    fallback_to_ping
        If ``True``, a system ping will be used if the user is not root or nmap
        is not available. This is less reliable than using nmap, but nmap requires
        running as root for reliable results.

    Returns
    -------
    is_up
        ``True`` if the host is up, ``False`` otherwise.

    """

    if not is_root():
        if fallback_to_ping:
            warnings.warn('Running as non-root; using "ping" instead of "nmap".')
            return await ping_host(host)
        raise PermissionError("root privileges are required to run nmap.")

    if not nmap3.get_nmap_path():
        if fallback_to_ping:
            warnings.warn('nmap not available. Using "ping instead.')
            return await ping_host(host)
        raise RuntimeError("nmap is not available.")

    nmap = nmap3.NmapHostDiscovery()
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
