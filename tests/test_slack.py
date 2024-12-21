#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-21
# @Filename: test_slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import lvmopstools.slack
from lvmopstools.slack import ICONS, post_message


if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture()
def mock_slack(mocker: MockerFixture):
    yield mocker.patch.object(lvmopstools.slack, "AsyncWebClient", autospec=True)


async def test_post_message(mock_slack):
    await post_message("@here This is a test", channel="test")

    mock_slack.return_value.chat_postMessage.assert_called_with(
        channel="test",
        text="<!here> This is a test",
        blocks=None,
        icon_url=None,
        username=None,
    )


async def test_post_message_with_icon(mock_slack):
    await post_message(
        "This is a test",
        channel="test",
        username="Overwatcher",
    )

    mock_slack.return_value.chat_postMessage.assert_called_with(
        channel="test",
        text="This is a test",
        blocks=None,
        icon_url=ICONS["overwatcher"],
        username="Overwatcher",
    )


async def test_post_message_with_user(mock_slack):
    mock_slack.return_value.users_list.return_value = {
        "members": [
            {
                "id": "U01ABC123",
                "name": "user1",
                "profile": {
                    "real_name": "User Name",
                    "display_name": "user1",
                    "display_name_normalized": "user1",
                },
            }
        ],
        "ok": True,
    }

    await post_message(
        "This is a test",
        channel="test",
        mentions=["user1"],
    )

    mock_slack.return_value.chat_postMessage.assert_called_with(
        channel="test",
        text="<@U01ABC123> This is a test",
        blocks=None,
        icon_url=None,
        username=None,
    )


async def test_post_message_raises(mock_slack):
    mock_slack.return_value.chat_postMessage.side_effect = (
        lvmopstools.slack.SlackApiError("test error", response={"error": "test error"})
    )

    with pytest.raises(RuntimeError):
        await post_message("This is a test", channel="test")


async def test_invalid_users_list(mock_slack):
    mock_slack.return_value.users_list.return_value = {"ok": False}

    with pytest.raises(RuntimeError):
        await lvmopstools.slack.get_user_list()


async def test_user_id_not_found(mock_slack):
    mock_slack.return_value.users_list.return_value = {
        "members": [
            {
                "id": "U01ABC123",
                "name": "user1",
                "profile": {
                    "real_name": "User Name",
                    "display_name": "user1",
                    "display_name_normalized": "user1",
                },
            }
        ],
        "ok": True,
    }

    with pytest.raises(NameError):
        await lvmopstools.slack.get_user_id("user2")
