"""RequestHandler Protocol definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Response


@runtime_checkable
class RequestHandler(Protocol):
    """Protocol for HTTP command handlers."""

    def get_handler_name(self) -> str:
        """Return the handler/command name (e.g., 'create', 'destroy', 'status')."""
        ...

    def handle(self, request: Request) -> Response:
        """Handle the request and return a response."""
        ...

    def unload(self) -> None:
        """Clean up handler resources."""
        ...
