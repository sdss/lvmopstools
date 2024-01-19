#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-18
# @Filename: ds9.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import pathlib
import re

from typing import TYPE_CHECKING

from clu import AMQPClient, AMQPReply


if TYPE_CHECKING:
    from pyds9 import DS9


CAMERAS = [
    "sci.west",
    "sci.east",
    "skye.west",
    "skye.east",
    "skyw.west",
    "skyw.east",
    "spec.east",
]


async def ds9_agcam_monitor(
    amqp_client: AMQPClient,
    cameras: list[str] | None = None,
    replace_path_prefix: tuple[str, str] | None = None,
):
    """Shows guider images in DS9."""

    images_handled = set([])

    # Clear all frames and get an instance of DS9.
    ds9 = ds9_clear_frames()

    if cameras is None:
        cameras = CAMERAS.copy()

    if len(cameras) == 0:
        raise ValueError("No cameras specified.")

    camera_to_filename: dict[str, str | pathlib.Path | None] = {}
    for cam in cameras:
        if cam not in CAMERAS:
            raise ValueError(f"Invalid camera {cam!r}. Valid cameras: {CAMERAS!r}.")
        camera_to_filename[cam] = None

    agcam_actors = set(["lvm." + (cam.split(".")[0]) + ".agcam" for cam in cameras])

    async def handle_reply(reply: AMQPReply):
        sender = reply.sender
        if sender not in agcam_actors:
            return

        if "filename" not in reply.body:
            return

        filename: str = reply.body["filename"]["filename"]
        if filename in images_handled:
            return

        images_handled.add(filename)

        if replace_path_prefix is not None:
            filename = filename.replace(replace_path_prefix[0], replace_path_prefix[1])

        telescope = sender.split(".")[1]
        camera = reply.body["filename"]["camera"]

        is_first_all = all([vv is None for vv in camera_to_filename.values()])
        is_first_camera = camera_to_filename[f"{telescope}.{camera}"] is None

        camera_to_filename[f"{telescope}.{camera}"] = filename

        ds9_display_frames(
            camera_to_filename,
            order=cameras,
            ds9=ds9,
            show_all_frames=False,
            preserve_frames=True,
            adjust_scale=is_first_camera,
            adjust_zoom=is_first_camera,
            show_tiles=is_first_all,
        )

    amqp_client.add_reply_callback(handle_reply)

    while True:
        await asyncio.sleep(1)


def ds9_clear_frames(ds9: DS9 | None = None, ds9_target: str = "DS9:*"):
    """Clears all frames in DS9."""

    try:
        import pyds9
    except ImportError:
        raise ImportError(
            "pyds9 is not installed. You can install it manually or run"
            "pip install lvmopstools[ds9]"
        )

    if ds9 is None:
        ds9 = pyds9.DS9(target=ds9_target)

    ds9.set("frame delete all")

    return ds9


def ds9_display_frames(
    files: list[str | pathlib.Path] | dict[str, str | pathlib.Path | None],
    ds9: DS9 | None = None,
    order=CAMERAS,
    ds9_target: str = "DS9:*",
    show_all_frames=True,
    preserve_frames=True,
    clear_frames=False,
    adjust_zoom=True,
    adjust_scale=True,
    show_tiles=True,
):
    """Displays a series of images in DS9."""

    try:
        import pyds9
    except ImportError:
        raise ImportError(
            "pyds9 is not installed. You can install it manually or run"
            "pip install lvmopstools[ds9]"
        )

    if ds9 is None:
        ds9 = pyds9.DS9(target=ds9_target)

    if clear_frames:
        ds9.set("frame delete all")

    files_dict: dict[str, str | None] = {}
    if not isinstance(files, dict):
        for file_ in files:
            tel_cam = parse_agcam_filename(file_)
            if tel_cam is None:
                raise ValueError(f"Cannot parse type of file {file_!s}.")
            files_dict[".".join(tel_cam)] = str(file_)
    else:
        files_dict = {k: str(v) if v is not None else None for k, v in files.items()}

    nframe = 1
    for cam in order:
        if cam in files_dict:
            ds9.set(f"frame {nframe}")

            has_file = ds9.get("file") != ""
            zoom = ds9.get("zoom")

            if has_file:
                ds9.set("preserve pan yes")
                ds9.set("preserve regions yes")
                ds9.set("preserve scale yes")

            file_ = files_dict[cam]
            if file_ is None:
                continue

            ds9.set(f"fits {file_}")

            if adjust_scale:
                ds9.set("scale log")
                ds9.set("scale minmax")

            if adjust_zoom:
                ds9.set("zoom to fit")
            elif has_file:
                ds9.set(f"zoom {zoom}")

            nframe += 1
        else:
            if show_all_frames:
                if preserve_frames is False:
                    ds9.set(f"frame {nframe}")
                    ds9.set("frame clear")
                nframe += 1

    if show_tiles:
        ds9.set("tile")

    return ds9


def parse_agcam_filename(file_: str | pathlib.Path):
    """Returns the type of an ``agcam`` file in the form ``(telescope, camera)``."""

    file_ = pathlib.Path(file_)
    basename = file_.name

    match = re.match(".+(sci|spec|skyw|skye).+(east|west)", basename)
    if not match:
        return None

    return match.groups()
