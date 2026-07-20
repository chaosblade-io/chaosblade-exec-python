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

"""Plugin Protocol definition."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.spi.enhancer import BeforeEnhancer, AfterEnhancer
    from chaosblade.spi.model_spec import ModelSpec
    from chaosblade.spi.point_cut import PointCut


@runtime_checkable
class Plugin(Protocol):
    """Plugin interface - the top-level registration unit for a chaos experiment target."""

    def get_name(self) -> str:
        """Return the plugin name."""
        ...

    def get_model_spec(self) -> ModelSpec:
        """Return the model specification for this plugin."""
        ...

    def get_point_cut(self) -> PointCut:
        """Return the point cut (interception point) for this plugin."""
        ...

    def get_enhancer(self) -> BeforeEnhancer | AfterEnhancer:
        """Return the enhancer (before/after advice) for this plugin."""
        ...
