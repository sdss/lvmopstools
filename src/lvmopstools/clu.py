#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-12
# @Filename: clu.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import os

from typing import TYPE_CHECKING, Any, Literal, overload

from clu.client import AMQPClient

from lvmopstools import config


if TYPE_CHECKING:
    from clu.command import Command


__all__ = ["CluClient", "send_clu_command"]


class CluClient:
    """AMQP client asynchronous generator.

    Returns an object with an ``AMQPClient`` instance. The normal way to
    use it is to do ::

        async with CluClient() as client:
            await client.send_command(...)

    Alternatively one can do ::

        client = await anext(CluClient())
        await client.send_command(...)

    The asynchronous generator differs from the one in ``AMQPClient`` in that
    it does not close the connection on exit.

    This class is a singleton, which effectively means the AMQP client is reused
    during the life of the worker. The singleton can be cleared by calling
    `.clear`.

    The host and port for the connection can be passed on initialisation. Otherwise
    it will use the values in the environment variables ``RABBITMQ_HOST`` and
    ``RABBITMQ_PORT`` or the default values in the configuration file.

    """

    __initialised: bool = False
    __instance: CluClient | None = None

    def __new__(cls, host: str | None = None, port: int | None = None):
        if (
            cls.__instance is None
            or (host is not None and cls.__instance.host != host)
            or (port is not None and cls.__instance.port != port)
        ):
            cls.clear()

            cls.__instance = super(CluClient, cls).__new__(cls)
            cls.__instance.__initialised = False

        return cls.__instance

    def __init__(self, host: str | None = None, port: int | None = None):
        if self.__initialised is True:
            # Bail out if we are returning a singleton instance
            # which is already initialised.
            return

        host_default = os.environ.get("RABBITMQ_HOST", config["rabbitmq.host"])
        port_default = int(os.environ.get("RABBITMQ_PORT", config["rabbitmq.port"]))

        self.host: str = host or host_default
        self.port: int = port or port_default

        self.client = AMQPClient(host=self.host, port=self.port)
        self.__initialised = True

        self._lock = asyncio.Lock()

    def is_connected(self):
        """Is the client connected?"""

        connection = self.client.connection
        connected = connection.connection and not connection.connection.is_closed
        channel_closed = hasattr(connection, "channel") and connection.channel.is_closed

        if not connected or channel_closed:
            return False

        return True

    async def __aenter__(self):
        # Small delay to allow the event loop to update the
        # connection status if needed.
        await asyncio.sleep(0.05)

        async with self._lock:
            if not self.is_connected():
                await self.client.start()

        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __anext__(self):
        if not self.is_connected():
            await self.client.start()

        return self.client

    @classmethod
    def clear(cls):
        """Clears the current instance."""

        if cls.__instance and cls.__instance.is_connected():
            asyncio.create_task(cls.__instance.client.stop())

        cls.__instance = None
        cls.__initialised = False


# @overload
# async def send_clu_command(command_string: str) -> list[dict[str, Any]]: ...


@overload
async def send_clu_command(
    command_string: str,
    *,
    raw: Literal[False] = False,
    internal: bool = False,
) -> list[dict[str, Any]]: ...


@overload
async def send_clu_command(
    command_string: str,
    *,
    raw: Literal[True] = True,
    internal: bool = False,
) -> Command: ...


async def send_clu_command(
    command_string: str,
    *,
    raw=False,
    internal: bool = False,
) -> list[dict[str, Any]] | Command:
    """Sends a command to the actor system and returns a list of replies.

    Parameters
    ----------
    command_string
        The command to send to the actor. Must include the name of the actor.
    raw
        If `True`, returns the command. Otherwise returns a list of replies.

    Returns
    -------
    replies
        A list of replies, each one a dictionary of keyword to value. Empty
        replies (e.g., those only changing the status) are not returned. If
        ``raw=True``, the CLU command is returned after awaiting for it to
        complete or fail.

    Raises
    ------
    RuntimeError
        If the command fails, times out, or is otherwise not successful.

    """

    consumer, *rest = command_string.split(" ")

    async with CluClient() as client:
        cmd = await client.send_command(consumer, " ".join(rest), internal=internal)

    if cmd.status.did_succeed:
        if raw:
            return cmd

        replies: list[dict[str, Any]] = []
        for reply in cmd.replies:
            if len(reply.message) == 0:
                continue
            replies.append(reply.message)
        return replies

    raise RuntimeError(f"Command {command_string!r} failed.")
