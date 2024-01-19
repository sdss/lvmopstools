#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-18
# @Filename: utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from clu import AMQPClient


async def get_amqp_client(**kwargs) -> AMQPClient:
    """Returns a CLU AMQP client."""

    amqp_client = AMQPClient(**kwargs)
    await amqp_client.start()

    return amqp_client
