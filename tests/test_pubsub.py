#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-21
# @Filename: test_pubsub.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

import pytest_mock

from lvmopstools.pubsub import Event, Subscriber, send_event


async def test_event_send_iterator(pubsub_subscriber: Subscriber):
    """Tests sending an event."""

    await send_event(Event.DOME_OPENING, payload={"foo": "bar"})

    await asyncio.sleep(0.05)

    async for event in pubsub_subscriber.iterator(decode=True):
        assert event.event == Event.DOME_OPENING
        assert event.event_name == "DOME_OPENING"
        assert event.payload == {"foo": "bar"}

        break


async def test_event_send_get(pubsub_subscriber: Subscriber):
    """Tests sending an event."""

    await send_event("DOME_STUCK", payload={"foo": "bar"})

    await asyncio.sleep(0.05)

    event = await pubsub_subscriber.get(decode=True)
    assert event.event == Event.UNCATEGORISED
    assert event.event_name == "DOME_STUCK"


async def test_event_callback(rabbitmq_client, mocker: pytest_mock.MockerFixture):
    """Tests sending an event."""

    callback = mocker.Mock()

    async with Subscriber(callback=callback):
        await send_event(Event.DOME_OPENING, payload={"foo": "bar"})

        await asyncio.sleep(0.05)

        callback.assert_called_once()
        assert callback.call_args[0][0].event == Event.DOME_OPENING
        assert callback.call_args[0][0].event_name == "DOME_OPENING"
        assert callback.call_args[0][0].payload == {"foo": "bar"}
