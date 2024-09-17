#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: thermistors.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import re

from typing import Literal, overload

import asyncudp

from lvmopstools import config
from lvmopstools.retrier import Retrier


__all__ = ["read_thermistors", "channel_to_valve"]


@overload
def channel_to_valve(reverse: Literal[False] = False) -> dict[int, str]: ...


@overload
def channel_to_valve(reverse: Literal[True] = True) -> dict[str, int]: ...


def channel_to_valve(reverse: bool = False) -> dict[int, str] | dict[str, int]:
    """Returns a mapping of thermistor channels to valve names.

    With ``reverse`` returns the inverse mapping, valve to device channel.

    """

    valve_to_channel = config["devices.thermistors.channels"]

    if reverse:
        return valve_to_channel

    channel_to_valve = {valve_to_channel[valve]: valve for valve in valve_to_channel}
    return channel_to_valve


@Retrier(max_attempts=3, delay=1)
async def read_thermistors():
    """Returns the thermistor values."""

    th_config = config["devices.thermistors"]

    host = th_config["host"]
    port = th_config["port"]

    socket: asyncudp.Socket | None = None

    try:
        socket = await asyncio.wait_for(
            asyncudp.create_socket(remote_addr=(host, port)),
            timeout=5,
        )

        socket.sendto(b"$016\r\n")
        data, _ = await asyncio.wait_for(socket.recvfrom(), timeout=10)
    finally:
        if socket:
            socket.close()

    match = re.match(rb"!01([0-9A-F]+)\r", data)
    if match is None:
        raise ValueError(f"Invalid response from thermistor server at {host!r}.")

    value = int(match.group(1), 16)

    thermistor_values: dict[str, bool] = {}
    for thermistor in th_config["channels"]:
        channel = th_config["channels"][thermistor]
        thermistor_values[thermistor] = bool(int((value & 1 << channel) > 0))

    return thermistor_values
