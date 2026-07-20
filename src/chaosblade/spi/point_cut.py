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

"""PointCut Protocol definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PointCut(Protocol):
    """Defines the interception point for a plugin."""

    def get_target_module(self) -> str:
        """Return the target module path, e.g. 'redis.client'."""
        ...

    def get_target_function(self) -> str:
        """Return the target function/method name, e.g. 'execute_command'."""
        ...

    def get_target_class(self) -> str | None:
        """Return the target class name, or None if targeting a module-level function."""
        ...
