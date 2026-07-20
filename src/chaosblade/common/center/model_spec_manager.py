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

"""ModelSpecManager - manages registered model specifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.model_spec import ModelSpec


class DefaultModelSpecManager:
    """Manages ModelSpec registrations indexed by target name."""

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = {}

    def register_model_spec(self, model_spec: ModelSpec) -> None:
        """Register a model spec by its target name."""
        self._specs[model_spec.get_target()] = model_spec

    def get_model_spec(self, target: str) -> ModelSpec | None:
        """Get a model spec by target name."""
        return self._specs.get(target)

    def list_all(self) -> list[ModelSpec]:
        """Return all registered model specs."""
        return list(self._specs.values())

    def get_all_targets(self) -> list[str]:
        """Return all registered target names."""
        return list(self._specs.keys())

    def load(self) -> None:
        """Initialize the manager."""
        pass

    def unload(self) -> None:
        """Clear all registrations."""
        self._specs.clear()
