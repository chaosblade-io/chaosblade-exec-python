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

"""HealthHandler - responds to /health requests with agent status."""

from __future__ import annotations

import platform
import sys
import time

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Response


_START_TIME = time.time()


class HealthHandler:
    """Handler for health check and status introspection."""

    def get_handler_name(self) -> str:
        return "health"

    def handle(self, request: Request) -> Response:
        """Return agent health status."""
        status_manager = ManagerFactory.get_status_manager()

        info = {
            "status": "running",
            "uptime_seconds": int(time.time() - _START_TIME),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "active_experiments": len(status_manager.get_all_uids()),
            "registered_targets": len(
                ManagerFactory.get_model_spec_manager().get_all_targets()
                if hasattr(ManagerFactory.get_model_spec_manager(), "get_all_targets")
                else []
            ),
        }

        return Response.of_success(info)

    def unload(self) -> None:
        pass
