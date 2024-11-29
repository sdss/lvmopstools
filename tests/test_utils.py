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
from lvmopstools.utils import is_notebook, with_timeout


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
