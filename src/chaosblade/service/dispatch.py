# Copyright 2025 The ChaosBlade Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DispatchService - routes HTTP requests to handlers."""

from __future__ import annotations

from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Code, Response
from chaosblade.service.handler.create_handler import CreateHandler
from chaosblade.service.handler.destroy_handler import DestroyHandler
from chaosblade.service.handler.health_handler import HealthHandler
from chaosblade.service.handler.list_handler import ListHandler
from chaosblade.service.handler.status_handler import StatusHandler


class DispatchService:
    """Routes incoming requests to the appropriate handler by command name."""

    def __init__(self) -> None:
        self._handlers: dict[str, any] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all built-in handlers."""
        for handler in (CreateHandler(), DestroyHandler(), StatusHandler(), ListHandler(), HealthHandler()):
            self._handlers[handler.get_handler_name()] = handler

    def dispatch(self, command: str, request: Request) -> Response:
        """Dispatch a request to the handler matching the command.

        Args:
            command: The command name (e.g., 'create', 'destroy', 'status').
            request: The parsed request with parameters.

        Returns:
            Response from the handler, or NOT_FOUND if command is unknown.
        """
        handler = self._handlers.get(command)
        if handler is None:
            return Response.of_failure(
                Code.NOT_FOUND, f"handler '{command}' not found"
            )
        return handler.handle(request)

    def unload(self) -> None:
        """Unload all handlers."""
        for handler in self._handlers.values():
            handler.unload()
