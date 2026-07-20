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

"""Shared base implementations for plugin components.

Provides concrete implementations of Protocol interfaces that plugins
can reuse instead of reimplementing from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.action_executor import ActionExecutor

from chaosblade.common.model.action_model import ActionModel
from chaosblade.common.model.predicate_result import PredicateResult


@dataclass
class DefaultFlagSpec:
    """Default implementation of FlagSpec."""

    _name: str
    _desc: str
    _required: bool = False
    _no_args: bool = False

    def get_name(self) -> str:
        return self._name

    def get_desc(self) -> str:
        return self._desc

    def is_required(self) -> bool:
        return self._required

    def no_args(self) -> bool:
        return self._no_args


@dataclass
class DefaultMatcherSpec:
    """Default implementation of MatcherSpec."""

    _name: str
    _desc: str
    _required: bool = False
    _no_args: bool = False

    def get_name(self) -> str:
        return self._name

    def get_desc(self) -> str:
        return self._desc

    def is_required(self) -> bool:
        return self._required

    def no_args(self) -> bool:
        return self._no_args


class DefaultActionSpec:
    """Default implementation of ActionSpec.

    Supports flag-based predicate validation and a pluggable executor.
    """

    def __init__(
        self,
        name: str,
        short_desc: str,
        long_desc: str = "",
        aliases: list[str] | None = None,
        flags: list[DefaultFlagSpec] | None = None,
        executor: ActionExecutor | None = None,
    ) -> None:
        self._name = name
        self._short_desc = short_desc
        self._long_desc = long_desc or short_desc
        self._aliases = aliases or []
        self._flags = flags or []
        self._executor = executor

    def get_name(self) -> str:
        return self._name

    def get_aliases(self) -> list[str]:
        return self._aliases

    def get_short_desc(self) -> str:
        return self._short_desc

    def get_long_desc(self) -> str:
        return self._long_desc

    def get_action_flags(self) -> list[DefaultFlagSpec]:
        return self._flags

    def predicate(self, action_model: ActionModel) -> PredicateResult:
        """Validate required flags are present."""
        for flag in self._flags:
            if flag.is_required():
                if action_model.get_flag(flag.get_name()) is None:
                    return PredicateResult.fail(
                        f"missing required flag: '{flag.get_name()}' for action '{self._name}'"
                    )
        return PredicateResult.ok()

    def get_action_executor(self) -> ActionExecutor:
        if self._executor is None:
            raise RuntimeError(f"No executor configured for action '{self._name}'")
        return self._executor


class DefaultPointCut:
    """Default implementation of PointCut."""

    def __init__(
        self,
        target_module: str,
        target_function: str,
        target_class: str | None = None,
    ) -> None:
        self._target_module = target_module
        self._target_function = target_function
        self._target_class = target_class

    def get_target_module(self) -> str:
        return self._target_module

    def get_target_function(self) -> str:
        return self._target_function

    def get_target_class(self) -> str | None:
        return self._target_class
