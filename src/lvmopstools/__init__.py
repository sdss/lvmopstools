#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-02
# @Filename: __init__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import pathlib
import warnings

from sdsstools import read_yaml_file
from sdsstools.metadata import get_package_version


__version__ = get_package_version(path=__file__, package_name="lvmopstools")


DEFAULT_CONFIG_FILE = pathlib.Path(__file__).parent / "config.yaml"
CONFIG_FILE = pathlib.Path(
    os.environ.get("LVMOPSTOOLS_CONFIG_FILE", DEFAULT_CONFIG_FILE)
)

if not CONFIG_FILE.exists():
    warnings.warn(
        f"Config file not found at {CONFIG_FILE!s}. "
        "Reverting to internal configuration."
    )
    CONFIG_FILE = DEFAULT_CONFIG_FILE


config = read_yaml_file(CONFIG_FILE)


def set_config(config_file: str | pathlib.Path | None = None) -> None:
    """Sets the configuration file."""

    global CONFIG_FILE

    config_path = pathlib.Path(config_file or DEFAULT_CONFIG_FILE)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file {config_path!s} not found.")

    config.load(config_path, use_base=False)

    CONFIG_FILE = config_path


from .retrier import *
from .socket import *
