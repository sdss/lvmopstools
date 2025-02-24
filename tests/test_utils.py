#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-29
# @Filename: test_utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

import pytest
import pytest_mock

import lvmopstools.utils
from lvmopstools.utils import Trigger, is_notebook, with_timeout


async def _timeout(delay: float):
    await asyncio.sleep(delay)
    return True


async def test_with_timeout():
    with pytest.raises(asyncio.TimeoutError):
        await with_timeout(_timeout(0.5), timeout=0.1)


async def test_with_timeout_no_raise():
    result = await with_timeout(_timeout(0.5), timeout=0.1, raise_on_timeout=False)
    assert result is None


class GetPythonMocker:
    def __init__(self, shell: str):
        self.shell = shell
        self.__class__.__name__ = shell

    def __call__(self):
        return self


@pytest.mark.parametrize(
    "shell, result",
    [
        ("ZMQInteractiveShell", True),
        ("TerminalInteractiveShell", False),
        ("other", False),
    ],
)
async def test_is_notebook(shell: str, result: bool, mocker: pytest_mock.MockerFixture):
    mocker.patch.object(
        lvmopstools.utils,
        "get_ipython",
        return_value=GetPythonMocker(shell),
        create=True,
    )

    assert is_notebook() == result


async def test_is_notebook_name_Error(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(
        lvmopstools.utils,
        "get_ipython",
        side_effect=NameError,
        create=True,
    )

    assert not is_notebook()


async def test_trigger_n_sets():
    trigger = Trigger(n=3)

    assert not trigger.is_set()

    trigger.set()
    assert not trigger.is_set()

    trigger.set()
    assert not trigger.is_set()

    trigger.set()
    assert trigger.is_set()


async def test_trigger_n_sets_delay():
    trigger = Trigger(n=2, delay=0.25)

    trigger.set()
    assert not trigger.is_set()

    trigger.set()
    assert not trigger.is_set()

    await asyncio.sleep(0.3)
    assert trigger.is_set()

    trigger.set()
    assert trigger.is_set()


async def test_trigger_reset():
    trigger = Trigger(n=2)

    trigger.set()
    trigger.set()
    assert trigger.is_set()

    trigger.reset()
    assert not trigger.is_set()

    trigger.set()
    trigger.reset()
    trigger.set()
    assert not trigger.is_set()


async def test_host_is_up(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(
        lvmopstools.utils.NmapHostDiscovery,
        "nmap_no_portscan",
        return_value={"host1": {"state": {"state": "up"}}},
    )

    assert await lvmopstools.utils.is_host_up("host1")


async def test_host_is_up_bad_reply(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(
        lvmopstools.utils.NmapHostDiscovery,
        "nmap_no_portscan",
        return_value={"host1": None},
    )

    assert (await lvmopstools.utils.is_host_up("host1")) is False
