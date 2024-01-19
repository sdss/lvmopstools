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


RequestFuncType = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[Any]]


@dataclass
class AsyncSocketHandler:
    """Handles a socket connection and disconnection."""

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
        """Sends a request to the socket."""

        return
