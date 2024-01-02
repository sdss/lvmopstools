#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-02
# @Filename: retrier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from typing import Callable


__all__ = ["Retrier", "retrier"]


@dataclass
class Retrier:
    """A class that implements a retry mechanism."""

    max_attempts: int = 3
    delay: float = 0.01

    def __call__(self, func: Callable):
        """Wraps a function to retry it if it fails."""

        is_coroutine = asyncio.iscoroutinefunction(func)

        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as ee:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        raise ee
                    else:
                        time.sleep(self.delay)

        async def async_wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as ee:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        raise ee
                    else:
                        await asyncio.sleep(self.delay)

        return wrapper if not is_coroutine else async_wrapper


# Mostly to use as a decorator and maintain the standard that functions are lowercase.
retrier = Retrier
