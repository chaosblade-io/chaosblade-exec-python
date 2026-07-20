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

"""ActionSpec Protocol definition."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.common.model.action_model import ActionModel
    from chaosblade.common.model.predicate_result import PredicateResult
    from chaosblade.spi.action_executor import ActionExecutor
    from chaosblade.spi.flag_spec import FlagSpec


@runtime_checkable
class ActionSpec(Protocol):
    """Specification for a chaos injection action (e.g., delay, exception, return)."""

    def get_name(self) -> str:
        """Return the canonical action name."""
        ...

    def get_aliases(self) -> list[str]:
        """Return action name aliases (e.g., ['mc'] for 'modifyCode')."""
        ...

    def get_short_desc(self) -> str:
        """Return a short description."""
        ...

    def get_long_desc(self) -> str:
        """Return a long description."""
        ...

    def get_action_flags(self) -> list[FlagSpec]:
        """Return the list of flags/parameters for this action."""
        ...

    def predicate(self, action_model: ActionModel) -> PredicateResult:
        """Validate the action parameters."""
        ...

    def get_action_executor(self) -> ActionExecutor:
        """Return the executor instance for this action."""
        ...
