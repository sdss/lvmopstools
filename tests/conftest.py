#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-10
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import contextlib
import pathlib

import pytest
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server.async_io import ServerAsyncStop, StartAsyncTcpServer
from pytest_mock import MockerFixture

from clu.testing import setup_test_actor

from lvmopstools import set_config
from lvmopstools.actor import ActorState, ErrorCodesBase, LVMActor


class TestActor(LVMActor):
    async def _check_internal(self):
        pass

    async def _troubleshoot_internal(
        self,
        error_code: ErrorCodesBase,
        exception: Exception | None = None,
    ):
        return True


@pytest.fixture(scope="session", autouse=True)
def monkeypatch_config():
    set_config(pathlib.Path(__file__).parent / "test_config.yaml")


@pytest.fixture()
async def lvm_actor(mocker: MockerFixture):
    actor = TestActor(name="test_actor", check_interval=1)

    await setup_test_actor(actor)  # type: ignore

    actor.update_state(ActorState.RUNNING)
    actor._check_task = asyncio.create_task(actor._check_loop())

    actor._check_internal = mocker.AsyncMock(return_value=None)
    actor._troubleshoot_internal = mocker.AsyncMock(return_value=True)
    actor.is_connected = mocker.MagicMock(return_value=True)

    yield actor

    await actor.stop()


@pytest.fixture(scope="function")
async def ion_pump_server():
    ir = [0] * 100

    # Set b2 voltage level to ~2V. There is something weird with pymodbus and although
    # we want the addresses set here to be 2 and 3 (0-indexed) we need to set 3 and 4.
    ir[3] = 0x3FFF
    ir[4] = 0x0

    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [0] * 100),
        ir=ModbusSequentialDataBlock(0, ir),
    )

    context = ModbusServerContext(slaves=store, single=True)

    task = asyncio.create_task(StartAsyncTcpServer(context, address=("0.0.0.0", 5020)))
    await asyncio.sleep(0.1)

    yield

    await ServerAsyncStop()

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
