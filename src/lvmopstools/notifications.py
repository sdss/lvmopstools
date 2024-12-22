#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-21
# @Filename: notifications.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import enum
import pathlib
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from typing import Any, Sequence, cast

from jinja2 import Environment, FileSystemLoader

from lvmopstools import config
from lvmopstools.slack import post_message as post_to_slack


__all__ = ["send_notification", "send_critical_error_email", "NotificationLevel"]


class NotificationLevel(enum.Enum):
    """Allowed notification levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


async def send_notification(
    message: str,
    level: NotificationLevel | str = NotificationLevel.INFO,
    slack: bool = True,
    slack_channels: str | Sequence[str] | None = None,
    email_on_critical: bool = True,
    slack_extra_params: dict[str, Any] = {},
    email_params: dict[str, Any] = {},
):
    """Creates a new notification.

    Parameters
    ----------
    message
        The message of the notification. Can be formatted in Markdown.
    level
        The level of the notification.
    slack
        Whether to send the notification to Slack.
    slack_channels
        The Slack channel where to send the notification. If not provided, the default
        channel is used. Can be set to false to disable sending the Slack notification.
    email_on_critical
        Whether to send an email if the notification level is ``CRITICAL``.
    slack_extra_params
        A dictionary of extra parameters to pass to ``post_message``.
    email_params
        A dictionary of extra parameters to pass to :obj:`.send_critical_error_email`.

    Returns
    -------
    message
        The message that was sent.

    """

    if isinstance(level, str):
        level = NotificationLevel(level.upper())
    else:
        level = NotificationLevel(level)

    send_email = email_on_critical and level == NotificationLevel.CRITICAL

    if send_email:
        try:
            send_critical_error_email(message, **email_params)
        except Exception as ee:
            print(f"Error sending critical error email: {ee}", file=sys.stderr)

    if slack:
        channels: set[str] = set()

        if isinstance(slack_channels, str):
            channels.add(slack_channels)
        elif isinstance(slack_channels, Sequence):
            channels.update(slack_channels)
        else:
            channels.add(config["slack.default_channel"])

        # We send the message to the default channel plus any other channel that
        # matches the level of the notification.
        level_channels = cast(dict[str, str], config["slack.level_channels"])
        if level.value in level_channels:
            channels.add(level_channels[level.value])

        # Send Slack message(s)
        for channel in channels:
            mentions = (
                ["@channel"]
                if level == NotificationLevel.CRITICAL
                or level == NotificationLevel.ERROR
                else []
            )
            try:
                await post_to_slack(
                    message,
                    channel=channel,
                    mentions=mentions,
                    **slack_extra_params,
                )
            except Exception as se:
                print(f"Error sending Slack message: {se}", file=sys.stderr)

    return message


def send_critical_error_email(
    message: str,
    host: str | None = None,
    port: int | None = None,
    tls: bool | None = None,
    username: str | None = None,
    password: str | None = None,
):
    """Sends a critical error email.

    Parameters
    ----------
    message
        The message to send.
    host
        The SMTP server host.
    port
        The SMTP server port.
    tls
        Whether to use TLS for authentication.
    username
        The SMTP server username.
    password
        The SMTP server password.

    """

    root = pathlib.Path(__file__).parent
    template = root / config["notifications.critical.email_template"]
    loader = FileSystemLoader(template.parent)

    env = Environment(
        loader=loader,
        lstrip_blocks=True,
        trim_blocks=True,
    )
    html_template = env.get_template(template.name)

    html_message = html_template.render(message=message.strip())

    recipients = config["notifications.critical.email_recipients"]
    from_address = config["notifications.critical.email_from"]

    email_reply_to = config["notifications.critical.email_reply_to"]

    msg = MIMEMultipart("alternative" if html_message else "mixed")
    msg["Subject"] = "LVM Critical Alert"
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = email_reply_to

    plaintext_email = f"""A critical alert was raised in the LVM system.

The error message is shown below:

{message}

"""
    msg.attach(MIMEText(plaintext_email, "plain"))

    html = MIMEText(html_message, "html")
    msg.attach(html)

    smtp_host = host or config["notifications.smtp_server.host"]
    smtp_port = port or config["notifications.smtp_server.port"]
    smpt_tls = tls if tls is not None else config["notifications.smtp_server.tls"]
    smtp_username = username or config["notifications.smtp_server.username"]
    smtp_password = password or config["notifications.smtp_server.password"]

    with smtplib.SMTP(host=smtp_host, port=smtp_port) as smtp:
        if smpt_tls is True or (smpt_tls is None and smtp_port == 587):
            # See https://gist.github.com/jamescalam/93d915e4de12e7f09834ae73bdf37299
            smtp.ehlo()
            smtp.starttls()

            if smtp_password is not None and smtp_password is not None:
                smtp.login(smtp_username, smtp_password)
            else:
                raise ValueError("username and password must be provided for TLS.")
        smtp.sendmail(from_address, recipients, msg.as_string())
