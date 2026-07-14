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
