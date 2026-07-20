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

"""SPI interface definitions for ChaosBlade Python executor."""

from chaosblade.spi.flag_spec import FlagSpec, MatcherSpec
from chaosblade.spi.custom_matcher import CustomMatcher
from chaosblade.spi.point_cut import PointCut
from chaosblade.spi.action_executor import (
    ActionExecutor,
    StoppableActionExecutor,
    DirectlyInjectionAction,
)
from chaosblade.spi.action_spec import ActionSpec
from chaosblade.spi.model_spec import (
    ModelSpec,
    PreCreateInjectionModelHandler,
    PreDestroyInjectionModelHandler,
)
from chaosblade.spi.enhancer import BeforeEnhancer, AfterEnhancer
from chaosblade.spi.plugin import Plugin

__all__ = [
    "FlagSpec",
    "MatcherSpec",
    "CustomMatcher",
    "PointCut",
    "ActionExecutor",
    "StoppableActionExecutor",
    "DirectlyInjectionAction",
    "ActionSpec",
    "ModelSpec",
    "PreCreateInjectionModelHandler",
    "PreDestroyInjectionModelHandler",
    "BeforeEnhancer",
    "AfterEnhancer",
    "Plugin",
]
