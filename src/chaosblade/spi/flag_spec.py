"""FlagSpec and MatcherSpec Protocol definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FlagSpec(Protocol):
    """Specification for a command-line flag/parameter."""

    def get_name(self) -> str:
        """Return the flag name."""
        ...

    def get_desc(self) -> str:
        """Return the flag description."""
        ...

    def is_required(self) -> bool:
        """Return whether this flag is required."""
        ...

    def no_args(self) -> bool:
        """Return whether this flag takes no arguments (boolean flag)."""
        ...


@runtime_checkable
class MatcherSpec(FlagSpec, Protocol):
    """Matcher specification, extends FlagSpec for ModelSpec matcher definitions."""

    pass
