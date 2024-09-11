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

from sdsstools.metadata import get_package_version, read_yaml_file


__version__ = get_package_version(path=__file__, package_name="lvmopstools")


DEFAULT_CONFIG_FILE = pathlib.Path(__file__).parent / "config.yaml"
CONFIG_FILE = os.environ.get("LVMOPSTOOLS_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))

config = read_yaml_file(CONFIG_FILE)


from .retrier import *
from .socket import *
