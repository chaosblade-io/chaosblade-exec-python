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

"""ModelSpec and lifecycle handler Protocol definitions."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.common.model.model import Model
    from chaosblade.common.model.predicate_result import PredicateResult
    from chaosblade.spi.action_spec import ActionSpec
    from chaosblade.spi.flag_spec import MatcherSpec


@runtime_checkable
class ModelSpec(Protocol):
    """Specification for an experiment target model (e.g., redis, flask, python)."""

    def get_target(self) -> str:
        """Return the target name (e.g., 'redis', 'flask')."""
        ...

    def get_short_desc(self) -> str:
        """Return a short description."""
        ...

    def get_long_desc(self) -> str:
        """Return a long description."""
        ...

    def get_actions(self) -> list[ActionSpec]:
        """Return all supported action specs."""
        ...

    def get_action_spec(self, name: str) -> ActionSpec | None:
        """Get action spec by name or alias."""
        ...

    def get_matcher_specs(self) -> list[MatcherSpec]:
        """Return matcher specs for this model."""
        ...

    def predicate(self, model: Model) -> PredicateResult:
        """Validate the model parameters."""
        ...

    def add_action_spec(self, action_spec: ActionSpec) -> None:
        """Register an action spec to this model."""
        ...


@runtime_checkable
class PreCreateInjectionModelHandler(Protocol):
    """Lifecycle hook called before experiment creation."""

    def pre_create(self, uid: str, model: Model) -> None:
        """Called before experiment is created."""
        ...


@runtime_checkable
class PreDestroyInjectionModelHandler(Protocol):
    """Lifecycle hook called before experiment destruction."""

    def pre_destroy(self, uid: str, model: Model) -> None:
        """Called before experiment is destroyed."""
        ...
