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

"""ActionExecutor, StoppableActionExecutor, and DirectlyInjectionAction Protocol definitions."""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel
    from chaosblade.common.model.model import Model


@runtime_checkable
class ActionExecutor(Protocol):
    """Executor that performs a chaos injection action."""

    def run(self, enhancer_model: EnhancerModel) -> None:
        """Execute the fault injection action."""
        ...


@runtime_checkable
class StoppableActionExecutor(ActionExecutor, Protocol):
    """Executor that can be stopped (for long-running injections like CPU/memory)."""

    def stop(self, enhancer_model: EnhancerModel) -> None:
        """Stop the running injection action."""
        ...


@runtime_checkable
class DirectlyInjectionAction(Protocol):
    """Action that executes directly at create/destroy time without needing an Enhancer."""

    def create_injection(self, uid: str, model: Model) -> None:
        """Create and start the injection immediately."""
        ...

    def destroy_injection(self, uid: str, model: Model) -> None:
        """Destroy and stop the injection immediately."""
        ...
