"""InterruptProcessException - control flow exception for fault injection."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ProcessState(Enum):
    """State indicating how to interrupt the target process."""

    RETURN_IMMEDIATELY = "return_immediately"
    THROWS_IMMEDIATELY = "throws_immediately"


class InterruptProcessException(Exception):
    """Control flow exception used to interrupt target method execution.

    When raised inside an Enhancer wrapper:
    - RETURN_IMMEDIATELY: return the response value to the caller
    - THROWS_IMMEDIATELY: raise the wrapped exception to the caller
    """

    __slots__ = ("_state", "_response", "_exception")

    def __init__(
        self,
        state: ProcessState,
        response: Any = None,
        exception: BaseException | None = None,
    ) -> None:
        super().__init__(str(state.value))
        self._state = state
        self._response = response
        self._exception = exception

    @property
    def state(self) -> ProcessState:
        """Return the process state."""
        return self._state

    @property
    def response(self) -> Any:
        """Return the response value (for RETURN_IMMEDIATELY)."""
        return self._response

    @property
    def exception(self) -> BaseException | None:
        """Return the exception (for THROWS_IMMEDIATELY)."""
        return self._exception


def throw_return_immediately(value: Any) -> None:
    """Raise InterruptProcessException to return a value immediately."""
    raise InterruptProcessException(ProcessState.RETURN_IMMEDIATELY, response=value)


def throw_immediately(exception: BaseException) -> None:
    """Raise InterruptProcessException to throw an exception immediately."""
    raise InterruptProcessException(ProcessState.THROWS_IMMEDIATELY, exception=exception)
