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

"""StatusHandler - handles experiment status query requests.

Ported from Java: chaosblade-exec-service/.../handler/StatusHandler.java
"""

from __future__ import annotations

import json

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Code, Response


class StatusHandler:
    """Handles /status requests to query experiment hit count by suid."""

    def __init__(self) -> None:
        self._unloaded = False

    def get_handler_name(self) -> str:
        return "status"

    def handle(self, request: Request) -> Response:
        """Handle a status query request."""
        if self._unloaded:
            return Response.of_failure(Code.ILLEGAL_STATE, "the agent is uninstalling")

        suid = request.get_param("suid")
        if not suid:
            return Response.of_failure(
                Code.ILLEGAL_PARAMETER, "missing required parameter: suid"
            )

        status_metric = ManagerFactory.get_status_manager().get_status_metric_by_uid(suid)
        if status_metric is None:
            return Response.of_failure(
                Code.NOT_FOUND, f"experiment with uid '{suid}' not found"
            )

        result = json.dumps({"count": status_metric.count})
        return Response.of_success(result)

    def unload(self) -> None:
        """Mark handler as unloaded."""
        self._unloaded = True
