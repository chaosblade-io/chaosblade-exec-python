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

"""ListHandler - lists all active experiments.

Provides a /list endpoint to query all currently active chaos experiments
with their uid, target, action, matchers, and hit count.
"""

from __future__ import annotations

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Response


class ListHandler:
    """Handles /list requests to enumerate all active experiments."""

    def __init__(self) -> None:
        self._unloaded = False

    def get_handler_name(self) -> str:
        return "list"

    def handle(self, request: Request) -> Response:
        """Return a list of all active experiments.

        Optional query params:
            target: filter by target name
            action: filter by action name (requires target)
        """
        if self._unloaded:
            return Response.of_failure(504, "the agent is uninstalling")

        status_manager = ManagerFactory.get_status_manager()
        filter_target = request.get_param("target")
        filter_action = request.get_param("action")

        experiments: list[dict] = []

        # Iterate all registered experiments
        for uid in status_manager.get_all_uids():
            metric = status_manager.get_status_metric_by_uid(uid)
            if metric is None:
                continue

            model = metric.model
            # Apply filters
            if filter_target and model.target != filter_target:
                continue
            if filter_action and model.action_name != filter_action:
                continue

            exp_info = {
                "uid": uid,
                "target": model.target,
                "action": model.action_name,
                "matchers": model.matcher.matchers,
                "hit_count": metric.count,
            }
            experiments.append(exp_info)

        return Response.of_success(experiments)

    def unload(self) -> None:
        """Mark handler as unloaded."""
        self._unloaded = True
