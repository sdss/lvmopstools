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
from functools import wraps

from typing import Any, Callable


__all__ = ["Retrier"]


@dataclass
class Retrier:
    """A class that implements a retry mechanism.

    The object returned by this class can be used to wrap a function that
    will be retried ``max_attempts`` times if it fails::

        def test_function():
            ...

        retrier = Retrier(max_attempts=5)
        retrier(test_function)()

    where the wrapped function can be a coroutine, in which case the wrapped function
    will also be a coroutine.

    Most frequently this class will be used as a decorator::

        @Retrier(max_attempts=4, delay=0.1)
        async def test_function(x, y):
            ...

        await test_function(1, 2)

    Parameters
    ----------
    max_attempts
        The maximum number of attempts before giving up.
    delay
        The delay between attempts, in seconds.
    raise_on_max_attempts
        Whether to raise an exception if the maximum number of attempts is reached.
        Otherwise the wrapped function will return :obj:`None` after the last attempt.
    use_exponential_backoff
        Whether to use exponential backoff for the delay between attempts. If
        :obj:`True`, the delay will be
        ``delay * exponential_backoff_base ** (attempt - 1) + random_ms`` where
        ``random_ms`` is a random number between 0 and 100 ms used to avoid
        synchronisation issues.
    exponential_backoff_base
        The base for the exponential backoff.
    max_delay
        The maximum delay between attempts when using exponential backoff.

    """

    max_attempts: int = 3
    delay: float = 1
    raise_on_max_attempts: bool = True
    use_exponential_backoff: bool = True
    exponential_backoff_base: float = 2
    max_delay: float = 32.0

    def calculate_delay(self, attempt: int) -> float:
        """Calculates the delay for a given attempt."""

        # Random number between 0 and 100 ms to avoid synchronisation issues.
        random_ms = 0.1 * (time.time() % 1)

        if self.use_exponential_backoff:
            return min(
                self.delay * self.exponential_backoff_base ** (attempt - 1) + random_ms,
                self.max_delay,
            )
        else:
            return self.delay

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wraps a function to retry it if it fails."""

        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as ee:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        if self.raise_on_max_attempts:
                            raise ee
                        return
                    else:
                        time.sleep(self.calculate_delay(attempt))

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as ee:
                    attempt += 1
                    if attempt >= self.max_attempts:
                        if self.raise_on_max_attempts:
                            raise ee
                        return
                    else:
                        await asyncio.sleep(self.calculate_delay(attempt))

        return wrapper if not is_coroutine else async_wrapper
