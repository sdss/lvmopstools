#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-02
# @Filename: test_retrier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from unittest.mock import MagicMock

from typing import Any, Awaitable, Callable, Literal, overload

import pytest

from lvmopstools import Retrier


@overload
def get_test_function(
    fail: bool = False,
    succeed_on: int = 2,
    async_: Literal[False] = False,
) -> Callable[..., Any]: ...


@overload
def get_test_function(
    fail: bool = False,
    succeed_on: int = 2,
    async_: Literal[True] = True,
) -> Callable[..., Awaitable[Any]]: ...


def get_test_function(
    fail: bool = False,
    succeed_on: int = 2,
    async_: bool = False,
) -> Callable[..., Any] | Callable[..., Awaitable[Any]]:
    global n_attempts

    n_attempts = 0

    def _inner():
        global n_attempts

        if fail:
            raise ValueError()

        n_attempts += 1
        if n_attempts == succeed_on:
            return True
        else:
            raise ValueError()

    def test_function():
        return _inner()

    async def test_function_async():
        return _inner()

    return test_function_async if async_ else test_function


on_retry_mock = MagicMock()


def _get_retrier(
    exponential_backoff: bool,
    on_retry: Callable[[Exception], None] | None = None,
):
    if exponential_backoff:
        base = 1.1
    else:
        base = 2

    return Retrier(
        use_exponential_backoff=exponential_backoff,
        exponential_backoff_base=base,
        on_retry=on_retry,
    )


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("exponential_backoff", [False, True])
@pytest.mark.parametrize("on_retry", [None, on_retry_mock])
def test_retrier(
    fail: bool,
    exponential_backoff: bool,
    on_retry: Callable[[Exception], None] | None,
):
    on_retry_mock.reset_mock()
    retrier = _get_retrier(exponential_backoff, on_retry=on_retry)
    test_function = retrier(get_test_function(async_=False, fail=fail))

    if fail:
        with pytest.raises(ValueError):
            test_function()
    else:
        assert test_function() is True
        if on_retry:
            assert on_retry_mock.call_count == 1
        else:
            assert on_retry_mock.call_count == 0


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("exponential_backoff", [False, True])
@pytest.mark.parametrize("on_retry", [None, on_retry_mock])
async def test_retrier_async(
    fail: bool,
    exponential_backoff: bool,
    on_retry: Callable[[Exception], None] | None,
):
    on_retry_mock.reset_mock()
    retrier = _get_retrier(exponential_backoff, on_retry=on_retry)
    test_function = retrier(get_test_function(async_=True, fail=fail))

    if fail:
        with pytest.raises(ValueError):
            await test_function()
    else:
        assert (await test_function()) is True
        if on_retry:
            assert on_retry_mock.call_count == 1
        else:
            assert on_retry_mock.call_count == 0
