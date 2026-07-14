"""PredicateResult - validation result container."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredicateResult:
    """Result of a predicate validation check."""

    success: bool
    error: str = ""

    @classmethod
    def ok(cls) -> PredicateResult:
        """Create a successful result."""
        return cls(success=True)

    @classmethod
    def fail(cls, msg: str) -> PredicateResult:
        """Create a failed result with error message."""
        return cls(success=False, error=msg)
