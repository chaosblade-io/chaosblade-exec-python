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

"""Model - the top-level experiment model containing target, matcher, and action."""

from __future__ import annotations

from chaosblade.common.model.action_model import ActionModel
from chaosblade.common.model.matcher_model import MatcherModel


class Model:
    """Represents a registered chaos experiment with target, matchers, and action."""

    __slots__ = ("_target", "_matcher", "_action")

    def __init__(self, target: str, action_name: str) -> None:
        self._target = target
        self._matcher = MatcherModel()
        self._action = ActionModel(action_name)

    @property
    def target(self) -> str:
        """Return the experiment target name."""
        return self._target

    @property
    def action_name(self) -> str:
        """Return the action name."""
        return self._action.name

    @property
    def action(self) -> ActionModel:
        """Return the action model."""
        return self._action

    @property
    def matcher(self) -> MatcherModel:
        """Return the matcher model."""
        return self._matcher

    @matcher.setter
    def matcher(self, value: MatcherModel) -> None:
        """Set the matcher model."""
        self._matcher = value

    def __repr__(self) -> str:
        return (
            f"Model(target={self._target!r}, action={self._action.name!r}, "
            f"matchers={self._matcher.matchers})"
        )

    def __str__(self) -> str:
        return self.__repr__()
