"""ActionExecutor, StoppableActionExecutor, and DirectlyInjectionAction Protocol definitions."""

from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel
    from chaosblade.common.model.model import Model


@runtime_checkable
class ActionExecutor(Protocol):
    """Executor that performs a chaos injection action."""

    def run(self, enhancer_model: EnhancerModel) -> None:
        """Execute the fault injection action."""
        ...


@runtime_checkable
class StoppableActionExecutor(ActionExecutor, Protocol):
    """Executor that can be stopped (for long-running injections like CPU/memory)."""

    def stop(self, enhancer_model: EnhancerModel) -> None:
        """Stop the running injection action."""
        ...


@runtime_checkable
class DirectlyInjectionAction(Protocol):
    """Action that executes directly at create/destroy time without needing an Enhancer."""

    def create_injection(self, uid: str, model: Model) -> None:
        """Create and start the injection immediately."""
        ...

    def destroy_injection(self, uid: str, model: Model) -> None:
        """Destroy and stop the injection immediately."""
        ...
