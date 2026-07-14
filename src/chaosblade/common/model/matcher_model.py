"""MatcherModel - key-value container for matcher parameters."""

from __future__ import annotations

from typing import Any


class MatcherModel:
    """Container for matcher key-value pairs used in experiment matching."""

    __slots__ = ("_matchers",)

    def __init__(self) -> None:
        self._matchers: dict[str, Any] = {}

    def add(self, key: str, value: Any) -> None:
        """Add a matcher key-value pair."""
        self._matchers[key] = value

    def get(self, key: str) -> Any | None:
        """Get a matcher value by key."""
        return self._matchers.get(key)

    @property
    def matchers(self) -> dict[str, Any]:
        """Return the internal matchers dict (not a copy, for performance)."""
        return self._matchers

    def __bool__(self) -> bool:
        """Return True if there are any matchers."""
        return bool(self._matchers)

    def __repr__(self) -> str:
        return f"MatcherModel({self._matchers})"
