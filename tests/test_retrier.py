#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-02
# @Filename: test_retrier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import pytest

from lvmopstools import retrier


@pytest.mark.parametrize("fail", [False, True])
async def test_retrier(fail: bool):
    global n_attempts

    n_attempts = 0

    @retrier(max_attempts=3)
    def test_function():
        global n_attempts

        if fail:
            raise ValueError()

        n_attempts += 1
        if n_attempts == 2:
            return True
        else:
            raise ValueError()

    if fail:
        with pytest.raises(ValueError):
            test_function()
    else:
        assert test_function() is True


@pytest.mark.parametrize("fail", [False, True])
async def test_retrier_async(fail: bool):
    global n_attempts

    n_attempts = 0

    @retrier(max_attempts=3)
    async def test_function():
        global n_attempts

        if fail:
            raise ValueError()

        n_attempts += 1
        if n_attempts == 2:
            return True
        else:
            raise ValueError()

    if fail:
        with pytest.raises(ValueError):
            await test_function()
    else:
        assert (await test_function()) is True
