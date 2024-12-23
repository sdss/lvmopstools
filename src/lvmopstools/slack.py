#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import re

from typing import Sequence

from aiocache import cached

from lvmopstools import config


try:
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web.async_client import AsyncWebClient
except ImportError:
    AsyncWebClient = None
    SlackApiError = None

__all__ = ["post_message", "get_user_id", "get_user_list"]


ICONS = {
    "overwatcher": "https://github.com/sdss/lvmgort/blob/main/docs/sphinx/_static/gort_logo_slack.png?raw=true"
}


def get_api_client(token: str | None = None):
    """Gets a Slack API client."""

    if AsyncWebClient is None:
        raise ImportError(
            "slack-sdk is not installed. Install the slack or all extras."
        )

    token = token or config["slack.token"] or os.environ["SLACK_API_TOKEN"]

    return AsyncWebClient(token=token)


async def format_mentions(text: str | None, mentions: list[str]) -> str | None:
    """Formats a text message with mentions."""

    if not text:
        return text

    if len(mentions) > 0:
        for mention in mentions[::-1]:
            if mention[0] != "@":
                mention = f"@{mention}"
            if mention not in text:
                text = f"{mention} {text}"

    # Replace @channel, @here, ... with the API format <!here>.
    text = re.sub(r"(\s|^)@(here|channel|everone)(\s|$)", r"\1<!here>\3", text)

    # The remaining mentions should be users. But in the API these need to be
    # <@XXXX> where XXXX is the user ID and not the username.
    users: list[str] = re.findall(r"(?:\s|^)@([a-zA-Z_0-9]+)(?:\s|$)", text)

    for user in users:
        try:
            user_id = await get_user_id(user)
        except NameError:
            continue
        text = text.replace(f"@{user}", f"<@{user_id}>")

    return text


async def post_message(
    text: str | None = None,
    blocks: Sequence[dict] | None = None,
    channel: str | None = None,
    mentions: list[str] = [],
    username: str | None = None,
    icon_url: str | None = None,
    **kwargs,
):
    """Posts a message to Slack.

    Parameters
    ----------
    text
        Plain text to send to the Slack channel.
    blocks
        A list of blocks to send to the Slack channel. These follow the Slack
        API format for blocks. Incompatible with ``text``.
    channel
        The channel in the SSDS-V workspace where to send the message.
    mentions
        A list of users to mention in the message.

    """

    if text is None and blocks is None:
        raise ValueError("Must specify either text or blocks.")

    if text is not None and blocks is not None:
        raise ValueError("Cannot specify both text and blocks.")

    channel = channel or config["slack.default_channel"]
    assert channel is not None

    if username is not None and icon_url is None and username.lower() in ICONS:
        icon_url = ICONS[username.lower()]

    client = get_api_client()
    assert SlackApiError is not None

    try:
        text = await format_mentions(text, mentions)
        await client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks,
            username=username,
            icon_url=icon_url,
            **kwargs,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack returned an error: {e.response['error']}")


@cached(ttl=120)
async def get_user_list():
    """Returns the list of users in the workspace.

    This function is cached because Slack limits the requests for this route.

    """

    client = get_api_client()
    assert SlackApiError is not None

    try:
        users_list = await client.users_list()
        if users_list["ok"] is False:
            err = "users_list returned ok=false"
            raise SlackApiError(err, response={"error": err})

        return users_list

    except SlackApiError as e:
        raise RuntimeError(f"Slack returned an error: {e.response['error']}")


async def get_user_id(name: str):
    """Gets the ``userID`` of the user display name matches ``name``."""

    users_list = await get_user_list()

    for member in users_list["members"]:
        if "profile" not in member or "display_name" not in member["profile"]:
            continue

        if (
            member["profile"]["display_name"] == name
            or member["profile"]["display_name_normalized"] == name
        ):
            return member["id"]

    raise NameError(f"User {name} not found.")
