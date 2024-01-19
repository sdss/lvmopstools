#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-17
# @Filename: socket.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from typing import Any, Awaitable, Callable

from lvmopstools.retrier import Retrier


__all__ = ["AsyncSocketHandler"]

RequestFuncType = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[Any]]


@dataclass
class AsyncSocketHandler:
    """Handles a socket connection and disconnection.

    Handles secure connection and disconnection to a TCP server and executed a
    callback. By default :obj:`.Retrier` is used to retry the connection if it
    fails either during the connection phase or during callback execution.

    There are two ways to use this class. The first one is to create an instance
    and call it with a callback function which receives :obj:`~asyncio.StreamReader`
    and :obj:`~asyncio.StreamWriter` arguments ::

            async def callback(reader, writer):
                ...

            handler = AsyncSocketHandler(host, port)
            await handler(callback)

    Alternatively, you can subclass ``AsyncSocketHandler`` and override the
    :obj:`request` method ::

        class MyHandler(AsyncSocketHandler):
            async def request(self, reader, writer):
                ...

    Parameters
    ----------
    host
        The host that is running the server.
    port
        The port on which the server is listening.
    timeout
        The timeout for connection and callback execution.
    retry
        Whether to retry the connection/callback if they fails.
    retrier_params
        Parameters to pass to the :class:`.Retrier` instance.

    """

    host: str
    port: int
    timeout: float = 5
    retry: bool = True
    retrier_params: dict[str, Any] = field(default_factory=dict)

    async def _connect(self):
        """Connects to the socket."""

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=self.timeout,
        )

        return reader, writer

    async def _run(self, func: RequestFuncType | None = None):
        """Internal helper to connect to the socket and run the request."""

        if func is None:
            func = self.request

        reader, writer = await self._connect()

        try:
            return await func(reader, writer)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def __call__(self, func: RequestFuncType | None = None):
        """Connects to the socket and runs the request function."""

        if self.retry:
            retrier = Retrier(**self.retrier_params)
            return await retrier(self._run)(func)
        else:
            return await self._run(func)

    async def request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):  # pragma: no cover
        """Sends a request to the socket.

        If the handler is not called with a callback function, this method must be
        overridden in a subclass. It receives the :obj:`~asyncio.StreamReader` and
        :obj:`~asyncio.StreamWriter` client instances after a connection has been
        established.

        """

        return
