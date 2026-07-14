"""Response - HTTP response with business code."""

from __future__ import annotations

import json
from enum import IntEnum
from typing import Any


class Code(IntEnum):
    """Business response codes (mapped from Java version)."""

    OK = 200
    NOT_FOUND = 404
    ILLEGAL_PARAMETER = 405
    DUPLICATE_INJECTION = 406
    SERVER_ERROR = 500
    ILLEGAL_STATE = 504


class Response:
    """Business response container with code, success flag, and result/error."""

    __slots__ = ("code", "success", "result", "error")

    def __init__(
        self,
        code: int,
        success: bool,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        self.code = code
        self.success = success
        self.result = result
        self.error = error

    @classmethod
    def of_success(cls, result: Any) -> Response:
        """Create a successful response with any serializable result."""
        return cls(code=Code.OK, success=True, result=result)

    @classmethod
    def of_failure(cls, code: Code, error: str) -> Response:
        """Create a failure response."""
        return cls(code=int(code), success=False, error=error)

    def to_dict(self) -> dict:
        """Convert to a dictionary for JSON serialization."""
        d: dict = {"code": self.code, "success": self.success}
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    def __repr__(self) -> str:
        return f"Response(code={self.code}, success={self.success}, result={self.result!r}, error={self.error!r})"
