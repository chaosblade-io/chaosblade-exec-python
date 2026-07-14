"""ActionModel - represents an action with its flags/parameters."""

from __future__ import annotations


class ActionModel:
    """Model representing a chaos action and its parameters."""

    __slots__ = ("_name", "_flags")

    def __init__(self, name: str) -> None:
        self._name = name
        self._flags: dict[str, str] = {}

    @property
    def name(self) -> str:
        """Return the action name."""
        return self._name

    def get_flag(self, key: str) -> str | None:
        """Get a flag value by key."""
        return self._flags.get(key)

    def add_flag(self, key: str, value: str) -> None:
        """Add or update a flag."""
        self._flags[key] = value

    @property
    def flags(self) -> dict[str, str]:
        """Return a copy of all flags."""
        return self._flags.copy()

    def __repr__(self) -> str:
        return f"ActionModel(name={self._name!r}, flags={self._flags})"
