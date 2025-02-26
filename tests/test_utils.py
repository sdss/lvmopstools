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
from lvmopstools.utils import (
    Trigger,
    is_host_up,
    is_notebook,
    power_cycle_ag_camera,
    with_timeout,
)


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
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=0)

    mocker.patch.object(
        lvmopstools.utils.nmap3,
        "get_nmap_path",
        return_value="/bin/nmap",
    )

    mocker.patch.object(
        lvmopstools.utils.nmap3.NmapHostDiscovery,
        "nmap_no_portscan",
        return_value={"host1": {"state": {"state": "up"}}},
    )

    assert await is_host_up("host1")


async def test_host_is_up_bad_reply(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=0)

    mocker.patch.object(
        lvmopstools.utils.nmap3,
        "get_nmap_path",
        return_value="/bin/nmap",
    )

    mocker.patch.object(
        lvmopstools.utils.nmap3.NmapHostDiscovery,
        "nmap_no_portscan",
        return_value={"host1": None},
    )

    assert (await is_host_up("host1")) is False


async def test_host_is_up_non_root(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=1)
    sp_mock = mocker.patch.object(lvmopstools.utils.asyncio, "create_subprocess_exec")
    wait_mock = sp_mock.return_value.wait
    wait_mock.return_value = 0

    assert await is_host_up("host1")
    sp_mock.assert_called()


async def test_host_is_up_no_use_ping(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=1)

    with pytest.raises(PermissionError):
        await is_host_up("host1", fallback_to_ping=False)


async def test_host_is_up_no_nmap(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=0)
    mocker.patch.object(lvmopstools.utils.nmap3, "get_nmap_path", return_value="")

    sp_mock = mocker.patch.object(lvmopstools.utils.asyncio, "create_subprocess_exec")
    wait_mock = sp_mock.return_value.wait
    wait_mock.return_value = 0

    assert await is_host_up("host1")
    sp_mock.assert_called()


async def test_host_is_up_no_nmap_no_use_ping(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.os, "geteuid", return_value=0)
    mocker.patch.object(lvmopstools.utils.nmap3, "get_nmap_path", return_value="")

    with pytest.raises(RuntimeError):
        await is_host_up("host1", fallback_to_ping=False)


@pytest.mark.parametrize("camera", ["CAM-111", 111, "sci-east"])
def test_power_cycle_ag_camera(
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    camera: str | int,
):
    monkeypatch.setenv("LVM_SWITCH_PASSWORD", "password")
    monkeypatch.setenv("LVM_SWITCH_SECRET", "secret")

    handler_mock = mocker.patch.object(lvmopstools.utils.netmiko, "ConnectHandler")
    send_config_set_mock = handler_mock.return_value.send_config_set

    power_cycle_ag_camera(camera, verbose=False)  # type: ignore
    send_config_set_mock.assert_called_with(["interface 2/0/6", "poe reset"])


def test_power_cycle_ag_camera_invalid_camera(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LVM_SWITCH_PASSWORD", "password")
    monkeypatch.setenv("LVM_SWITCH_SECRET", "secret")

    with pytest.raises(ValueError):
        power_cycle_ag_camera("abcd")


def test_power_cycle_ag_camera_no_password():
    with pytest.raises(ValueError) as err:
        power_cycle_ag_camera("CAM-111")

    assert "$LVM_SWITCH_PASSWORD has not been set." in str(err.value)


def test_power_cycle_ag_camera_no_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LVM_SWITCH_PASSWORD", "password")

    with pytest.raises(ValueError) as err:
        power_cycle_ag_camera("CAM-111")

    assert "$LVM_SWITCH_SECRET has not been set." in str(err.value)


def test_power_cycle_ag_camera_no_paramiko(mocker: pytest_mock.MockerFixture):
    mocker.patch.object(lvmopstools.utils, "netmiko", None)

    with pytest.raises(ImportError) as err:
        power_cycle_ag_camera("CAM-111")

    assert "netmiko is required to power cycle the switch port." in str(err.value)
