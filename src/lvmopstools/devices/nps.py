#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-09-13
# @Filename: nps.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TypedDict

from sdsstools import GatheringTaskGroup

from lvmopstools.clu import send_clu_command
from lvmopstools.retrier import Retrier


__all__ = ["read_nps"]


class NPSStatus(TypedDict):
    """A class to represent the status of an NPS."""

    actor: str
    name: str
    id: int
    state: bool


@Retrier(max_attempts=3, delay=1)
async def read_nps() -> dict[str, NPSStatus]:
    """Returns the status of all NPS."""

    actors = ["lvmnps.sp1", "lvmnps.sp2", "lvmnps.sp3", "lvmnps.calib"]

    async with GatheringTaskGroup() as group:
        for actor in actors:
            group.create_task(
                send_clu_command(
                    f"{actor} status",
                    raw=True,
                    internal=True,
                )
            )

    nps_data: dict[str, NPSStatus] = {}

    for cmd in group.results():
        actor = cmd.consumer_id
        outlets = cmd.replies.get("outlets")
        for outlet in outlets:
            key = f"{actor.split('.')[1]}.{outlet['normalised_name']}"
            nps_data[key] = NPSStatus(
                actor=actor,
                name=outlet["normalised_name"],
                id=outlet["id"],
                state=outlet["state"],
            )

    return nps_data
