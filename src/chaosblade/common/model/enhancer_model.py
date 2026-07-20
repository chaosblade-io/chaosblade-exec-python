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

"""EnhancerModel - runtime context model built by Enhancer for Injector matching."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.custom_matcher import CustomMatcher

from chaosblade.common.model.action_model import ActionModel
from chaosblade.common.model.matcher_model import MatcherModel


class EnhancerModel:
    """Runtime model constructed by Enhancer, carrying method context and matcher values.

    The Injector uses this to compare against registered experiment models.
    """

    __slots__ = (
        "target",
        "_action_model",
        "_matcher_model",
        "_custom_matchers",
        "_method_name",
        "_obj",
        "_args",
        "_kwargs",
        "_return_value",
        "_timeout_executor",
    )

    def __init__(self, matcher_model: MatcherModel | None = None) -> None:
        self.target: str = ""
        self._action_model: ActionModel | None = None
        self._matcher_model = matcher_model or MatcherModel()
        self._custom_matchers: dict[str, CustomMatcher] = {}
        self._method_name: str = ""
        self._obj: Any = None
        self._args: tuple = ()
        self._kwargs: dict[str, Any] = {}
        self._return_value: Any = None
        self._timeout_executor: Any = None

    @property
    def matcher_model(self) -> MatcherModel:
        """Return the matcher model with actual runtime values."""
        return self._matcher_model

    def get_action_flag(self, key: str) -> str | None:
        """Get an action flag value (available after merge)."""
        if self._action_model is None:
            return None
        return self._action_model.get_flag(key)

    @property
    def action_model(self) -> ActionModel | None:
        """Return the action model (set after merge)."""
        return self._action_model

    def add_custom_matcher(self, key: str, value: Any, matcher: CustomMatcher) -> None:
        """Add a custom matcher with its actual value."""
        self._matcher_model.add(key, value)
        self._custom_matchers[key] = matcher

    def get_matcher(self, key: str) -> CustomMatcher | None:
        """Get a custom matcher by key."""
        return self._custom_matchers.get(key)

    def merge(self, model: Any) -> None:
        """Merge experiment model's action flags into this enhancer model.

        Args:
            model: A Model instance whose action will be adopted.
        """
        self._action_model = model.action

    # --- Method context properties ---

    @property
    def method_name(self) -> str:
        return self._method_name

    @method_name.setter
    def method_name(self, value: str) -> None:
        self._method_name = value

    @property
    def obj(self) -> Any:
        return self._obj

    @obj.setter
    def obj(self, value: Any) -> None:
        self._obj = value

    @property
    def args(self) -> tuple:
        return self._args

    @args.setter
    def args(self, value: tuple) -> None:
        self._args = value

    @property
    def kwargs(self) -> dict[str, Any]:
        return self._kwargs

    @kwargs.setter
    def kwargs(self, value: dict[str, Any]) -> None:
        self._kwargs = value

    @property
    def return_value(self) -> Any:
        return self._return_value

    @return_value.setter
    def return_value(self, value: Any) -> None:
        self._return_value = value

    @property
    def timeout_executor(self) -> Any:
        return self._timeout_executor

    @timeout_executor.setter
    def timeout_executor(self, value: Any) -> None:
        self._timeout_executor = value

    def __repr__(self) -> str:
        return (
            f"EnhancerModel(target={self.target!r}, method={self._method_name!r}, "
            f"matchers={self._matcher_model.matchers})"
        )
