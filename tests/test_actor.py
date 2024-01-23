#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-22
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import enum
import sys

import pytest
from pytest_mock import MockerFixture

from sdsstools import cancel_task

import lvmopstools.actor
from lvmopstools.actor import (
    ActorState,
    CheckError,
    ErrorCodes,
    ErrorData,
    LVMActor,
    extend_enum,
    verify_error_codes,
)


def test_extend_enum():
    @extend_enum(ErrorCodes)
    class ExtraErrorCodes(enum.Enum):
        SOME_FAILURE_MODE = ErrorData(1, critical=False, description="Test error")

    assert hasattr(ExtraErrorCodes, "SOME_FAILURE_MODE")
    assert hasattr(ExtraErrorCodes, "UNKNOWN")

    assert hasattr(ExtraErrorCodes, "get_error_code")


def test_verify_error_codes_fails():
    with pytest.raises(ValueError):

        @verify_error_codes()
        class NewErrorCodes(enum.Enum):
            SOME_FAILURE_MODE = 1


async def test_actor_state(lvm_actor: LVMActor):
    assert isinstance(lvm_actor, LVMActor)

    cmd = await lvm_actor.invoke_mock_command("actor-state")
    await cmd

    assert cmd.status.did_succeed

    lvm_actor._check_internal.assert_called_once()
    lvm_actor._troubleshoot_internal.assert_not_called()


async def test_actor_state_no_model(lvm_actor: LVMActor):
    assert isinstance(lvm_actor, LVMActor)

    lvm_actor.model = None

    cmd = await lvm_actor.invoke_mock_command("actor-state")
    await cmd

    assert cmd.status.did_succeed
    assert cmd.replies[-1].body["state"]["code"] is not None
    assert cmd.replies[-1].body["state"]["error"] is None


def test_get_error_codes():
    assert ErrorCodes.UNKNOWN == ErrorCodes.get_error_code(9999)


def test_get_error_codes_not_valid():
    with pytest.raises(ValueError):
        ErrorCodes.get_error_code(999999)


@pytest.mark.parametrize(
    "side_effect",
    [
        ValueError("Test error"),
        CheckError("Test error", ErrorCodes.UNKNOWN),
        CheckError("Test error", 9999),
    ],
)
async def test_actor_check_fails(lvm_actor: LVMActor, mocker, side_effect: Exception):
    lvm_actor._check_internal = mocker.AsyncMock(side_effect=side_effect)

    # Restart the check loop
    await cancel_task(lvm_actor._check_task)
    lvm_actor._check_task = asyncio.create_task(lvm_actor._check_loop())

    await asyncio.sleep(0.1)

    replies = lvm_actor.mock_replies  # type: ignore
    assert len(replies) == 4

    assert not (replies[0]["state"]["code"] & ActorState.READY.value)
    assert replies[1]["state"]["code"] & ActorState.READY.value
    assert replies[2]["state"]["code"] & ActorState.TROUBLESHOOTING.value
    assert replies[3]["state"]["code"] & ActorState.READY.value

    assert replies[1]["state"]["flags"] == ["RUNNING", "READY"]


async def test_actor_restart(lvm_actor: LVMActor, mocker: MockerFixture):
    lvm_actor.restart_after = 2
    lvm_actor._check_internal = mocker.AsyncMock(side_effect=ValueError("Test error"))
    lvm_actor._troubleshoot_internal = mocker.AsyncMock(return_value=False)

    mock_restart = lvm_actor.restart = mocker.AsyncMock(return_value=None)

    await asyncio.sleep(3.5)

    mock_restart.assert_called_once()


async def test_actor_restart_exit(lvm_actor: LVMActor, mocker: MockerFixture):
    mocker.patch.object(lvmopstools.actor, "stop_event_loop")
    mock_exit = mocker.patch.object(sys, "exit")

    await lvm_actor.restart(mode="exit")
    mock_exit.assert_called_once_with(1)


async def test_actor_restart_reload(lvm_actor: LVMActor, mocker: MockerFixture):
    lvm_actor.start = mocker.AsyncMock()
    lvm_actor.stop = mocker.AsyncMock()

    await lvm_actor.restart(mode="reload")
    lvm_actor.start.assert_called()
    lvm_actor.stop.assert_called()


async def test_actor_restart_bad_mode(lvm_actor: LVMActor):
    with pytest.raises(ValueError):
        await lvm_actor.restart(mode="bad_mode")
