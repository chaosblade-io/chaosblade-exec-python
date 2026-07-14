"""PointCut Protocol definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PointCut(Protocol):
    """Defines the interception point for a plugin."""

    def get_target_module(self) -> str:
        """Return the target module path, e.g. 'redis.client'."""
        ...

    def get_target_function(self) -> str:
        """Return the target function/method name, e.g. 'execute_command'."""
        ...

    def get_target_class(self) -> str | None:
        """Return the target class name, or None if targeting a module-level function."""
        ...
