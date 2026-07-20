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

"""CreateHandler - handles experiment creation requests.

Ported from Java: chaosblade-exec-service/.../handler/CreateHandler.java
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.model_spec import ModelSpec

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.common.model.model import Model
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Code, Response
from chaosblade.spi.action_executor import DirectlyInjectionAction
from chaosblade.spi.model_spec import (
    PreCreateInjectionModelHandler,
    PreDestroyInjectionModelHandler,
)

logger = logging.getLogger(__name__)

# Reserved parameter keys (not part of matchers)
_RESERVED_KEYS = frozenset({"suid", "target", "action", "debug"})


class CreateHandler:
    """Handles /create requests to register and start chaos experiments.

    Flow:
    1. Validate required parameters (suid, target, action)
    2. Handle debug flag
    3. Look up ModelSpec and ActionSpec
    4. Parse request params into Model
    5. Run predicate validation
    6. Register experiment
    7. Handle DirectlyInjectionAction or lazy-load plugin
    8. Call pre_create lifecycle hook
    """

    def __init__(self) -> None:
        self._unloaded = False

    def get_handler_name(self) -> str:
        return "create"

    def handle(self, request: Request) -> Response:
        """Handle a create experiment request."""
        if self._unloaded:
            return Response.of_failure(Code.ILLEGAL_STATE, "the agent is uninstalling")

        # 1. Validate required parameters
        suid = request.get_param("suid")
        if not suid:
            return Response.of_failure(Code.ILLEGAL_PARAMETER, "missing required parameter: suid")

        target = request.get_param("target")
        if not target:
            return Response.of_failure(Code.ILLEGAL_PARAMETER, "missing required parameter: target")

        action = request.get_param("action")
        if not action:
            return Response.of_failure(Code.ILLEGAL_PARAMETER, "missing required parameter: action")

        # 2. Handle debug flag
        debug = request.get_param("debug")
        if debug and debug.lower() == "true":
            logging.getLogger("chaosblade").setLevel(logging.DEBUG)
        else:
            logging.getLogger("chaosblade").setLevel(logging.INFO)

        # 3. Look up ModelSpec
        model_spec = ManagerFactory.get_model_spec_manager().get_model_spec(target)
        if model_spec is None:
            return Response.of_failure(
                Code.NOT_FOUND, f"target '{target}' not supported"
            )

        # 4. Look up ActionSpec
        action_spec = model_spec.get_action_spec(action)
        if action_spec is None:
            return Response.of_failure(
                Code.NOT_FOUND, f"action '{action}' not supported for target '{target}'"
            )

        # 5. Parse Model from request (pass action_spec to distinguish flags from matchers)
        model = self._parse_model(target, action, request, action_spec)

        # 6. Predicate validation
        predicate_result = model_spec.predicate(model)
        if not predicate_result.success:
            return Response.of_failure(Code.ILLEGAL_PARAMETER, predicate_result.error)

        # 7. Handle injection
        return self._handle_injection(suid, model, model_spec, action_spec)

    def _parse_model(self, target: str, action: str, request: Request, action_spec: any = None) -> Model:
        """Parse request parameters into a Model.

        Separates action flags from matchers:
        - Parameters that match a defined ActionSpec flag → action flags only
        - All other parameters → both action flags AND matchers (for Injector matching)
        """
        model = Model(target, action)

        # Collect known action flag names from the ActionSpec
        action_flag_names: set[str] = set()
        if action_spec is not None:
            flags = getattr(action_spec, "get_action_flags", None)
            if flags is not None:
                for flag in flags():
                    action_flag_names.add(flag.get_name())

        for key, value in request.params.items():
            if key in _RESERVED_KEYS:
                continue
            # Always store as action flag
            model.action.add_flag(key, value)
            # Only add to matcher if it's NOT a known action flag
            if key not in action_flag_names:
                model.matcher.add(key, value)

        return model

    def _handle_injection(
        self, suid: str, model: Model, model_spec: ModelSpec, action_spec: any
    ) -> Response:
        """Register experiment and trigger injection."""
        # Check for DirectlyInjectionAction
        executor = action_spec.get_action_executor()
        if isinstance(executor, DirectlyInjectionAction):
            # Register first
            result = ManagerFactory.get_status_manager().register_exp(suid, model)
            if not result.success:
                return Response.of_failure(Code.DUPLICATE_INJECTION, result.message)
            try:
                executor.create_injection(suid, model)
                self._apply_pre_create(suid, model_spec, model)
                return Response.of_success(str(model))
            except Exception as e:
                ManagerFactory.get_status_manager().remove_exp(suid)
                return Response.of_failure(Code.SERVER_ERROR, str(e))

        # Normal injection path
        result = ManagerFactory.get_status_manager().register_exp(suid, model)
        if not result.success:
            return Response.of_failure(Code.DUPLICATE_INJECTION, result.message)

        try:
            self._lazy_load_plugin(model_spec, model)
            self._apply_pre_create(suid, model_spec, model)
        except Exception as e:
            ManagerFactory.get_status_manager().remove_exp(suid)
            return Response.of_failure(Code.SERVER_ERROR, str(e))

        return Response.of_success(str(model))

    def _lazy_load_plugin(self, model_spec: ModelSpec, model: Model) -> None:
        """Lazy-load the plugin if not already loaded."""
        target = model_spec.get_target()
        plugin_manager = ManagerFactory.get_plugin_manager()
        plugin_beans = plugin_manager.get_plugins(target)

        if plugin_beans is None or plugin_beans.loaded:
            return

        # Mark as loaded and notify listener
        plugin_manager.set_load(plugin_beans, target)
        listener = ManagerFactory.get_listener_manager().get_plugin_lifecycle_listener()
        if listener is not None:
            for plugin_bean in plugin_beans.plugin_beans:
                listener.add(plugin_bean)

    def _apply_pre_create(self, uid: str, model_spec: ModelSpec, model: Model) -> None:
        """Call pre_create lifecycle hook if the ModelSpec implements it."""
        if isinstance(model_spec, PreCreateInjectionModelHandler):
            model_spec.pre_create(uid, model)

    def unload(self) -> None:
        """Mark handler as unloaded."""
        self._unloaded = True
