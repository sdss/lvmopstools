#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-10
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

import pytest
from pytest_mock import MockerFixture

from clu.testing import setup_test_actor

from lvmopstools.actor import ActorState, ErrorCodes, LVMActor


class TestActor(LVMActor):
    async def _check_internal(self):
        pass

    async def _troubleshoot_internal(
        self,
        error_code: ErrorCodes,
        exception: Exception | None = None,
    ):
        return True


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
