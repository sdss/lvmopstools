#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-02
# @Filename: test_retrier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pytest

from lvmopstools import Retrier


def get_test_function(async_: bool = False, fail: bool = False, succeed_on: int = 2):
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


def _get_retrier(raise_: bool, exponential_backoff: bool):
    if exponential_backoff:
        base = 1.1
    else:
        base = 2

    return Retrier(
        raise_on_max_attempts=raise_,
        use_exponential_backoff=exponential_backoff,
        exponential_backoff_base=base,
    )


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("raise_", [False, True])
@pytest.mark.parametrize("exponential_backoff", [False, True])
def test_retrier(fail: bool, raise_: bool, exponential_backoff: bool):
    retrier = _get_retrier(raise_, exponential_backoff)
    test_function = retrier(get_test_function(async_=False, fail=fail))

    if fail:
        if raise_:
            with pytest.raises(ValueError):
                test_function()
        else:
            assert test_function() is None
    else:
        assert test_function() is True


@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("raise_", [False, True])
@pytest.mark.parametrize("exponential_backoff", [False, True])
async def test_retrier_async(fail: bool, raise_: bool, exponential_backoff: bool):
    retrier = _get_retrier(raise_, exponential_backoff)
    test_function = retrier(get_test_function(async_=True, fail=fail))

    if fail:
        if raise_:
            with pytest.raises(ValueError):
                await test_function()
        else:
            assert (await test_function()) is None
    else:
        assert (await test_function()) is True
