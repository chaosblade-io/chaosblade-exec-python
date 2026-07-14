"""Request - HTTP request parameter container."""

from __future__ import annotations


class Request:
    """Container for HTTP request parameters."""

    __slots__ = ("_params",)

    def __init__(self, params: dict[str, str] | None = None) -> None:
        self._params: dict[str, str] = params or {}

    def get_param(self, key: str) -> str | None:
        """Get a parameter value by key."""
        return self._params.get(key)

    @property
    def params(self) -> dict[str, str]:
        """Return all parameters."""
        return self._params

    def __repr__(self) -> str:
        return f"Request(params={self._params})"
