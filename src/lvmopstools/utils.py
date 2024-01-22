#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-18
# @Filename: utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from typing import Any

from clu import AMQPClient


__all__ = ["get_amqp_client", "get_exception_data", "stop_event_loop"]


async def get_amqp_client(**kwargs) -> AMQPClient:
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


async def stop_event_loop(timeout: float | None = 5):
    """Cancels all running tasks and stops the event loop."""

    for task in asyncio.all_tasks():
        task.cancel()

    try:
        await asyncio.wait_for(asyncio.gather(*asyncio.all_tasks()), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        asyncio.get_running_loop().stop()
