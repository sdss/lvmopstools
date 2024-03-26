#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-01-20
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import abc
import asyncio
import enum
import sys
import time
from dataclasses import dataclass

from typing import Any

import click

from clu.actor import AMQPActor
from clu.command import Command
from clu.parsers.click import CluCommand
from sdsstools import cancel_task

from lvmopstools.utils import get_exception_data, stop_event_loop


__all__ = [
    "LVMActor",
    "CheckError",
    "ActorState",
    "ErrorCodes",
    "ErrorCodesBase",
    "ErrorData",
    "create_error_codes",
]


STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "integer"},
        "flags": {"type": "array", "items": {"type": "string"}},
        "error": {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "code": {"type": "integer"},
                        "critical": {"type": "boolean"},
                        "description": {
                            "oneOf": [{"type": "string"}, {"type": "null"}]
                        },
                        "exception": {"oneOf": [{"type": "object"}, {"type": "null"}]},
                    },
                    "required": ["code", "critical", "description"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        },
        "additionalProperties": False,
    },
}


class ActorState(enum.Flag):
    """Defines the possible states of the actor."""

    RUNNING = 1 << 0
    READY = 1 << 1
    TROUBLESHOOTING = 1 << 2
    TROUBLESHOOT_FAILED = 1 << 3
    RESTARTING = 1 << 4
    CHECKING = 1 << 5

    NOT_READY = TROUBLESHOOTING | TROUBLESHOOT_FAILED | RESTARTING
    SKIP_CHECK = CHECKING | TROUBLESHOOTING | RESTARTING

    def get_state_names(self):
        """Returns the state names that are set."""

        return [state.name for state in self.__class__ if self & state]


@dataclass
class ErrorData:
    code: int
    critical: bool = False
    description: str = ""


class ErrorCodesBase(enum.Enum):
    """Enumeration of error codes"""

    @classmethod
    def get_error_code(cls, error_code: int):
        """Returns the :obj:`.ErrorCodes` that matches the ``error_code`` value."""

        for error in cls:
            if error.value.code == error_code:
                return error

        raise ValueError(f"Error code {error_code} not found.")


def create_error_codes(
    error_codes: dict[str, tuple | list | ErrorData],
    name: str = "ErrorCodes",
    include_unknown: bool = True,
) -> Any:
    """Creates an enumeration of error codes."""

    error_codes_enum: dict[str, ErrorData] = {}
    for error_name, error_data in error_codes.items():
        if not isinstance(error_data, ErrorData):
            error_data = ErrorData(*error_data)
        error_codes_enum[error_name.upper()] = error_data

    if include_unknown and "UNKNOWN" not in error_codes_enum:
        error_codes_enum["UNKNOWN"] = ErrorData(9999, True, "Unknown error")

    return ErrorCodesBase(name, error_codes_enum)


ErrorCodes = create_error_codes({"UNKNOWN": ErrorData(9999, True, "Unknown error")})


@click.command(cls=CluCommand, name="actor-state")
async def actor_state(command: Command[LVMActor], *args, **kwargs):
    """Returns the actor state."""

    state = command.actor.state
    code = state.value
    flags = state.get_state_names()

    if (model := command.actor.model) is not None:
        state_kw = model["state"]
        if state_kw is not None and state_kw.value:
            state = state_kw.value.copy()
            state.update({"code": code, "flags": flags})
            return command.finish(state=state)

    return command.finish(state={"code": code, "flags": flags, "error": None})


@click.command(cls=CluCommand, name="actor-restart")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["exit", "reload"]),
    default="exit",
    help="How to restart the actor.",
)
async def actor_restart(command: Command[LVMActor], mode: str = "exit"):
    """Restarts the actor."""

    await command.actor.restart(mode=mode)
    return command.finish()


class CheckError(Exception):
    """An exception raised when the :obj:`.LVMActor` check fails."""

    def __init__(
        self,
        message: str = "",
        error_code: ErrorCodesBase | int = ErrorCodes.UNKNOWN,
    ):
        if isinstance(error_code, int):
            self.error_code = ErrorCodes.get_error_code(error_code)
        else:
            self.error_code = error_code

        self.message = message

        super().__init__(message)


class LVMActor(AMQPActor):
    """Base class for LVM actors."""

    def __init__(
        self,
        *args,
        check_interval: float = 30.0,
        restart_after: float | None = 300.0,
        restart_mode="reload",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Actor state.
        self.state = ActorState(0)
        self.check_interval = check_interval
        self._check_task: asyncio.Task | None = None
        self._last_not_ready: float = -1

        self.restart_after = restart_after
        self.restart_mode = restart_mode

        # Additional commands.
        self.parser.add_command(actor_state)
        self.parser.add_command(actor_restart)

        # Add keywords in schema for the actor state.
        assert self.model and self.model.schema, "Model schema not defined"
        self.model.schema["properties"]["state"] = STATE_SCHEMA

    async def start(self):  # pragma: no cover
        """Starts the actor."""

        await super().start()
        self.update_state(ActorState.RUNNING)

        self._check_task = asyncio.create_task(self._check_loop())

        return self

    async def stop(self):
        """Stops the actor."""

        await cancel_task(self._check_task)
        await self.timed_commands.stop()

        return await super().stop()

    async def _check_loop(self):
        """Runs the check loop."""

        while True:
            if self.state & ActorState.SKIP_CHECK:
                await asyncio.sleep(self.check_interval)
                continue

            if not self.is_ready() and self._last_not_ready > 0:
                not_ready_time = time.time() - self._last_not_ready
                if self.restart_after and not_ready_time > self.restart_after:
                    self.write(
                        "w",
                        text=f"It has been {not_ready_time:.0f} seconds since the "
                        "actor was last ready. Restarting.",
                    )
                    await self.restart()

            try:
                self.state |= ActorState.CHECKING
                await self._check_internal()
            except CheckError as err:
                await self.troubleshoot(error_code=err.error_code, exception=err)
            except Exception as err:
                await self.troubleshoot(exception=err, traceback_frame=1)
            else:
                self.update_state(ActorState.READY)
            finally:
                await asyncio.sleep(self.check_interval)

    def is_ready(self):
        """Returns :obj:`True` if the actor is ready."""

        return bool(self.state & ActorState.READY)

    def update_state(
        self,
        state: ActorState,
        error_data: dict[str, Any] | None = None,
        command: Command | None = None,
        internal: bool = True,
    ):
        """Updates the state and broadcasts the change."""

        old_state = self.state

        self.state = ActorState(0)
        self.state |= state

        if self.state & ActorState.NOT_READY:
            self.state &= ~ActorState.READY
            if self._last_not_ready < 0:
                self._last_not_ready = time.time()
        else:
            self._last_not_ready = -1

        if self.is_connected():
            self.state |= ActorState.RUNNING

        if old_state != self.state:
            self.write(
                "d",
                state={
                    "code": self.state.value,
                    "flags": self.state.get_state_names(),
                    "error": error_data,
                },
                internal=internal,
                command=command,
            )

        return self.state

    async def troubleshoot(
        self,
        error_code: ErrorCodesBase = ErrorCodes.UNKNOWN,
        exception: Exception | None = None,
        traceback_frame: int = 0,
    ):
        """Handles troubleshooting."""

        error_data = {
            "code": error_code.value.code,
            "critical": error_code.value.critical,
            "description": error_code.value.description,
            "exception": get_exception_data(exception, traceback_frame=traceback_frame),
        }

        self.update_state(ActorState.TROUBLESHOOTING, error_data=error_data)

        if await self._troubleshoot_internal(error_code, exception=exception):
            self.update_state(ActorState.READY)
        else:
            self.update_state(ActorState.TROUBLESHOOT_FAILED)

    async def restart(self, mode: str | None = None):
        """Restarts the actor by killing the process.

        Parameters
        ----------
        mode
            How to restart the actor. Possible values are ``"exit"``, which will
            finish the process and let the supervisor restart it (for example
            a Kubernetes scheduler), and ``"reload"`` which will stop and restart
            the actor without killing the process. If ``None``, defaults to
            ``restart_mode``.

        """

        mode = mode or self.restart_mode

        self.write("w", text=f"Restarting {self.name} with mode={mode!r}.")
        self.update_state(ActorState.RESTARTING)

        await asyncio.sleep(1)

        if mode == "exit":
            await stop_event_loop()
            sys.exit(1)
        elif mode == "reload":
            try:
                await self.stop()
            finally:
                await self.start()
        else:
            raise ValueError("Invalid restart mode.")

    @abc.abstractmethod
    async def _check_internal(self):
        """Checks the status of the actor.

        This method is intended for the user to override when subclassing from
        :obj:`.LVMActor`. It is called by :obj:`.check_loop` every ``check_interval``
        seconds. The method must perform any necessary checks and, if a problem
        is found, call :obj:`.troubleshoot` with the appropriate error code.
        Alternatively if the check fails it can raise a :obj:`.CheckError` with
        the appropriate error code.

        """

        pass

    @abc.abstractmethod
    async def _troubleshoot_internal(
        self,
        error_code: ErrorCodesBase,
        exception: Exception | None = None,
    ):
        """Handles internal troubleshooting.

        This methos is intended for the user to override when subclassing from
        :obj:`.LVMActor`. It is called by :obj:`.troubleshoot` after updating
        the actor state to :obj:`.State.TROUBLESHOOTING`.

        The method must perform any necessary troubleshooting and then return
        a boolean indicating whether the actor is ready to continue or not.
        :obj:`.troubleshoot` will then update the actor state accordingly.

        """

        return False
