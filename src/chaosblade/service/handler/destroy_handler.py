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

"""DestroyHandler - handles experiment destruction requests.

Ported from Java: chaosblade-exec-service/.../handler/DestroyHandler.java
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.model_spec import ModelSpec

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Code, Response
from chaosblade.spi.action_executor import DirectlyInjectionAction
from chaosblade.spi.model_spec import PreDestroyInjectionModelHandler

logger = logging.getLogger(__name__)


class DestroyHandler:
    """Handles /destroy requests to stop and remove chaos experiments.

    Supports two modes:
    1. By uid: destroy a specific experiment
    2. By target + action: destroy all experiments matching target and action
    """

    def __init__(self) -> None:
        self._unloaded = False

    def get_handler_name(self) -> str:
        return "destroy"

    def handle(self, request: Request) -> Response:
        """Handle a destroy experiment request."""
        if self._unloaded:
            return Response.of_failure(Code.ILLEGAL_STATE, "the agent is uninstalling")

        uid = request.get_param("suid")
        target = request.get_param("target")
        action = request.get_param("action")

        # Mode 1: Destroy by uid
        if uid:
            return self._destroy_by_uid(uid)

        # Mode 2: Destroy by target + action
        if not target:
            return Response.of_failure(
                Code.ILLEGAL_PARAMETER,
                "missing required parameter: suid or target",
            )
        if not action:
            return Response.of_failure(
                Code.ILLEGAL_PARAMETER,
                "missing required parameter: action (when destroying by target)",
            )

        return self._destroy_by_target_action(target, action)

    def _destroy_by_uid(self, uid: str) -> Response:
        """Destroy a single experiment by uid."""
        status_manager = ManagerFactory.get_status_manager()
        model = status_manager.remove_exp(uid)

        if model is None:
            return Response.of_failure(
                Code.NOT_FOUND, f"experiment with uid '{uid}' not found"
            )

        self._post_destroy(uid, model)
        return Response.of_success(f"destroy experiment '{uid}' successfully")

    def _destroy_by_target_action(self, target: str, action: str) -> Response:
        """Destroy all experiments matching target and action."""
        status_manager = ManagerFactory.get_status_manager()
        uids = status_manager.list_uids(target, action)

        if not uids:
            return Response.of_failure(
                Code.NOT_FOUND,
                f"no experiments found for target '{target}' action '{action}'",
            )

        for uid in uids:
            model = status_manager.remove_exp(uid)
            if model is not None:
                self._post_destroy(uid, model)

        return Response.of_success(
            f"destroy {len(uids)} experiment(s) for target '{target}' action '{action}'"
        )

    def _post_destroy(self, uid: str, model: any) -> None:
        """Post-destroy: call DirectlyInjectionAction.destroy and pre_destroy hook."""
        target = model.target
        model_spec = ManagerFactory.get_model_spec_manager().get_model_spec(target)

        if model_spec is not None:
            # Call DirectlyInjectionAction.destroy_injection if applicable
            action_spec = model_spec.get_action_spec(model.action_name)
            if action_spec is not None:
                executor = action_spec.get_action_executor()
                if isinstance(executor, DirectlyInjectionAction):
                    try:
                        executor.destroy_injection(uid, model)
                    except Exception:
                        logger.warning(
                            "Error in destroy_injection for uid=%s", uid, exc_info=True
                        )

            # Call pre_destroy lifecycle hook
            if isinstance(model_spec, PreDestroyInjectionModelHandler):
                try:
                    model_spec.pre_destroy(uid, model)
                except Exception:
                    logger.warning(
                        "Error in pre_destroy for uid=%s", uid, exc_info=True
                    )

    def unload(self) -> None:
        """Mark handler as unloaded."""
        self._unloaded = True
