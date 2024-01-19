#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-19
# @Filename: test_socket.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

import pytest

from lvmopstools.socket import AsyncSocketHandler


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    data = await reader.readline()
    if data == b"hello\n":
        writer.write(b"hello there\n")
        await writer.drain()
    writer.close()


@pytest.fixture()
async def socket_server(unused_tcp_port: int):
    server = await asyncio.start_server(handle_connection, "0.0.0.0", unused_tcp_port)

    yield unused_tcp_port

    server.close()
    await server.wait_closed()


async def _say_hi(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    writer.write(b"hello\n")
    await writer.drain()

    data = await reader.readline()
    return data


class TestSocket(AsyncSocketHandler):
    async def request(self, reader, writer):
        return await _say_hi(reader, writer)


@pytest.mark.parametrize("retry", [True, False])
async def test_socket(socket_server, unused_tcp_port: int, retry: bool):
    socker_handler = AsyncSocketHandler("127.0.0.1", unused_tcp_port, retry=retry)

    response = await socker_handler(_say_hi)
    assert response == b"hello there\n"


@pytest.mark.parametrize("retry", [True, False])
async def test_socket_override(socket_server, unused_tcp_port: int, retry: bool):
    socker_handler = TestSocket("127.0.0.1", unused_tcp_port, retry=retry)

    response = await socker_handler()
    assert response == b"hello there\n"
