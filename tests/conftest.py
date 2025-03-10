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
import os
import pathlib
import socket

import pytest
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import ServerAsyncStop, StartAsyncTcpServer
from pytest_mock import MockerFixture
from pytest_rabbitmq.factories import rabbitmq, rabbitmq_proc

from clu.testing import setup_test_actor

from lvmopstools import set_config
from lvmopstools.actor import ActorState, ErrorCodesBase, LVMActor
from lvmopstools.pubsub import Subscriber


class TestActor(LVMActor):
    async def _check_internal(self):
        pass

    async def _troubleshoot_internal(
        self,
        error_code: ErrorCodesBase,
        exception: Exception | None = None,
    ):
        return True


def get_free_port():
    """Returns a free port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def setup_rabbitmq(port: int | None = None):
    """Sets up a RabbitMQ server for testing either locally or in CI."""

    DEFAULT_CTL = "/opt/homebrew/opt/rabbitmq/sbin/rabbitmqctl"
    DEFAULT_SERVER = "/opt/homebrew/opt/rabbitmq/sbin/rabbitmq-server"

    env_ctl = os.environ.get("PYTEST_RABBITMQ_CTL", DEFAULT_CTL)
    env_server = os.environ.get("PYTEST_RABBITMQ_SERVER", DEFAULT_SERVER)

    rabbit_ctl = env_ctl or DEFAULT_CTL
    rabbit_server = env_server or DEFAULT_SERVER
    rabbit_host = "127.0.0.1"

    return rabbitmq_proc(
        host=rabbit_host,
        ctl=rabbit_ctl,
        server=rabbit_server,
        port=port or get_free_port(),
    )


rabbitmq_port = get_free_port()
rabbitmq_proc_custom = setup_rabbitmq(rabbitmq_port)
rabbitmq_client = rabbitmq("rabbitmq_proc_custom")


@pytest.fixture(scope="session", autouse=True)
def monkeypatch_config(tmp_path_factory: pytest.TempPathFactory):
    # Replace the placeholder in the test config file with the actual RMQ port.
    test_config_path = pathlib.Path(__file__).parent / "data" / "test_config.yaml"
    test_config = test_config_path.read_text()
    test_config = test_config.replace("<random-port>", str(rabbitmq_port))

    test_config_tmp_path = tmp_path_factory.mktemp("lvmopstools") / "test_config.yaml"
    test_config_tmp_path.write_text(test_config)

    set_config(test_config_tmp_path)


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


@pytest.fixture(scope="function")
async def pubsub_subscriber(rabbitmq_client):
    subscriber = Subscriber()
    await subscriber.connect()

    if subscriber.queue:
        await subscriber.queue.purge()

    yield subscriber

    await subscriber.disconnect()
