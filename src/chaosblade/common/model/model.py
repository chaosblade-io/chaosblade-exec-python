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
