#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-18
# @Filename: __main__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import click

from sdsstools.daemonizer import cli_coro


@click.group()
def lvmopstools():
    """LVM operations tools."""

    pass


@lvmopstools.command()
@click.argument("CAMERAS", type=str, nargs=-1)
@cli_coro()
async def monitor_agcam(cameras: list[str]):
    """Monitors AGCam images in DS9."""

    from lvmopstools.ds9 import ds9_agcam_monitor
    from lvmopstools.utils import get_amqp_client

    client = await get_amqp_client()

    await ds9_agcam_monitor(client, cameras=cameras)


if __name__ == "__main__":
    lvmopstools()
