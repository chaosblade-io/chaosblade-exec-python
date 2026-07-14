"""BaseModelSpec - abstract base for ModelSpec implementations with alias support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.action_spec import ActionSpec
    from chaosblade.spi.flag_spec import MatcherSpec

from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult


class BaseModelSpec(ABC):
    """Base ModelSpec implementation with action spec management and predicate validation.

    Handles:
    - Action spec registration with alias mapping
    - Parameter validation via predicate()
    """

    def __init__(self) -> None:
        self._action_specs: dict[str, ActionSpec] = {}
        self._alias_map: dict[str, str] = {}  # alias -> canonical name

    @abstractmethod
    def get_target(self) -> str:
        """Return the target name."""
        ...

    @abstractmethod
    def get_short_desc(self) -> str:
        """Return a short description."""
        ...

    @abstractmethod
    def get_long_desc(self) -> str:
        """Return a long description."""
        ...

    @abstractmethod
    def get_matcher_specs(self) -> list[MatcherSpec]:
        """Return matcher specs for this model."""
        ...

    def get_actions(self) -> list[ActionSpec]:
        """Return all registered action specs."""
        return list(self._action_specs.values())

    def get_action_spec(self, name: str) -> ActionSpec | None:
        """Get action spec by name or alias (O(1) lookup)."""
        spec = self._action_specs.get(name)
        if spec is not None:
            return spec
        canonical = self._alias_map.get(name)
        if canonical is not None:
            return self._action_specs.get(canonical)
        return None

    def add_action_spec(self, action_spec: ActionSpec) -> None:
        """Register an action spec with its aliases."""
        name = action_spec.get_name()
        self._action_specs[name] = action_spec
        for alias in action_spec.get_aliases():
            self._alias_map[alias] = name

    def predicate(self, model: Model) -> PredicateResult:
        """Validate model parameters.

        Checks:
        1. Action spec exists (by name or alias)
        2. Action-level predicate passes
        3. Required matcher specs are provided
        """
        action_spec = self.get_action_spec(model.action_name)
        if action_spec is None:
            return PredicateResult.fail(
                f"action '{model.action_name}' not supported for target '{self.get_target()}'"
            )

        action_predicate = action_spec.predicate(model.action)
        if not action_predicate.success:
            return action_predicate

        # Check required matcher specs
        for matcher_spec in self.get_matcher_specs():
            if matcher_spec.is_required():
                if model.matcher.get(matcher_spec.get_name()) is None:
                    return PredicateResult.fail(
                        f"missing required matcher: '{matcher_spec.get_name()}'"
                    )

        return PredicateResult.ok()
