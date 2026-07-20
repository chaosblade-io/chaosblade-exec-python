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
