"""CustomMatcher Protocol definition."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CustomMatcher(Protocol):
    """Custom matcher for complex parameter matching logic."""

    def match(self, rule_value: str, actual_value: Any) -> bool:
        """Match rule value against actual value."""
        ...

    def regex_match(self, pattern: str, actual_value: Any) -> bool:
        """Match using regex pattern against actual value."""
        ...
