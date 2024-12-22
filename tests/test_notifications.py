#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-21
# @Filename: test_notifications.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from lvmopstools.notifications import (
    NotificationLevel,
    send_critical_error_email,
    send_notification,
)


if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.parametrize("level", ["INFO", "CRITICAL", NotificationLevel.DEBUG])
async def test_send_notification(mocker: MockerFixture, level: str | NotificationLevel):
    slack_mock = mocker.patch("lvmopstools.notifications.post_to_slack")
    email_mock = mocker.patch("lvmopstools.notifications.send_critical_error_email")

    message = await send_notification("test message", level=level)

    assert message == "test message"
    slack_mock.assert_called_with(
        "test message",
        channel=mocker.ANY,
        mentions=["@channel"] if level == "CRITICAL" else [],
    )

    if level == "CRITICAL":
        email_mock.assert_called()
    else:
        email_mock.assert_not_called()


@pytest.mark.parametrize(
    "level,channels,n_calls,",
    [
        ("INFO", None, 1),
        ("INFO", "test-channel", 1),
        ("INFO", ["test-channel", "test-channel2"], 2),
        ("CRITICAL", None, 2),
        ("CRITICAL", "test-channel", 2),
    ],
)
async def test_send_notification_channels(
    mocker: MockerFixture,
    level: str | NotificationLevel,
    channels: str | list[str],
    n_calls: int,
):
    slack_mock = mocker.patch("lvmopstools.notifications.post_to_slack")
    email_mock = mocker.patch("lvmopstools.notifications.send_critical_error_email")

    await send_notification(
        "test message",
        level=level,
        slack_channels=channels,
        slack=True,
    )

    assert slack_mock.call_count == n_calls

    if level == "CRITICAL":
        email_mock.assert_called()
    else:
        email_mock.assert_not_called()


async def test_send_notification_no_slack(mocker: MockerFixture):
    slack_mock = mocker.patch("lvmopstools.notifications.post_to_slack")

    await send_notification("test message", slack=False)

    slack_mock.assert_not_called()


async def test_send_notification_no_email(mocker: MockerFixture):
    email_mock = mocker.patch("lvmopstools.notifications.send_critical_error_email")

    await send_notification(
        "test message",
        email_on_critical=False,
        level="CRITICAL",
        slack=False,
    )

    email_mock.assert_not_called()


async def test_post_to_slack_fails(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
):
    mocker.patch("lvmopstools.notifications.post_to_slack", side_effect=ValueError())

    await send_notification("test message", slack=True)

    stderr = capsys.readouterr().err
    assert "Error sending Slack message" in stderr


async def test_send_email_fails(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture,
):
    mocker.patch(
        "lvmopstools.notifications.send_critical_error_email",
        side_effect=ValueError(),
    )

    await send_notification("test message", level="CRITICAL")

    stderr = capsys.readouterr().err
    assert "Error sending critical error email" in stderr


def test_send_email(mocker: MockerFixture):
    smtp_mock = mocker.patch("lvmopstools.notifications.smtplib.SMTP", autospec=True)
    sendmail_mock = smtp_mock.return_value.__enter__.return_value.sendmail

    send_critical_error_email("test message")

    sendmail_mock.assert_called()
    assert "Content-Type: multipart/alternative" in sendmail_mock.call_args[0][-1]
    assert "<html>" in sendmail_mock.call_args[0][-1]


def test_send_email_tls(mocker: MockerFixture):
    smtp_mock = mocker.patch("lvmopstools.notifications.smtplib.SMTP", autospec=True)
    sendmail_mock = smtp_mock.return_value.__enter__.return_value.sendmail

    send_critical_error_email(
        "test message",
        tls=True,
        username="test",
        password="test",
    )

    sendmail_mock.assert_called()
    smtp_mock.return_value.__enter__.return_value.starttls.assert_called()


def test_send_email_tls_no_password(mocker: MockerFixture):
    mocker.patch("lvmopstools.notifications.smtplib.SMTP", autospec=True)

    with pytest.raises(ValueError):
        send_critical_error_email(
            "test message",
            tls=True,
            username="test",
        )
