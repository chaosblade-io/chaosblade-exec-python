"""StatusManager - manages active experiment registrations and metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.model import Model


@dataclass
class RegisterResult:
    """Result of an experiment registration attempt."""

    success: bool
    message: str = ""


class StatusMetric:
    """Experiment status metric: holds a Model and its hit count.

    Thread-safe via internal lock for count operations.
    """

    __slots__ = ("_model", "_count", "_lock")

    def __init__(self, model: Model) -> None:
        self._model = model
        self._count: int = 0
        self._lock = threading.Lock()

    @property
    def model(self) -> Model:
        """Return the experiment model."""
        return self._model

    @property
    def count(self) -> int:
        """Return the current hit count."""
        return self._count

    def increase(self) -> None:
        """Increment hit count."""
        with self._lock:
            self._count += 1

    def decrease(self) -> None:
        """Decrement hit count (on executor failure rollback)."""
        with self._lock:
            if self._count > 0:
                self._count -= 1

    def increase_with_lock(self, limit: int) -> bool:
        """Atomically increment count if below limit.

        Returns True if increment was successful, False if limit reached.
        """
        with self._lock:
            if self._count >= limit:
                return False
            self._count += 1
            return True


class DefaultStatusManager:
    """Thread-safe experiment status manager.

    Manages active experiments indexed by uid, with lookup by target.
    """

    def __init__(self) -> None:
        self._experiments: dict[str, StatusMetric] = {}  # uid -> StatusMetric
        self._lock = threading.Lock()

    def register_exp(self, uid: str, model: Model) -> RegisterResult:
        """Register an experiment. Returns failure if uid already exists."""
        with self._lock:
            if uid in self._experiments:
                return RegisterResult(
                    success=False,
                    message=f"experiment with uid '{uid}' already exists",
                )
            self._experiments[uid] = StatusMetric(model)
            return RegisterResult(success=True)

    def remove_exp(self, uid: str) -> Model | None:
        """Remove an experiment by uid. Returns the model if found."""
        with self._lock:
            metric = self._experiments.pop(uid, None)
            return metric.model if metric else None

    def exp_exists(self, target: str) -> bool:
        """Check if any active experiment exists for the given target."""
        with self._lock:
            return any(
                m.model.target == target for m in self._experiments.values()
            )

    def get_exp_by_target(self, target: str) -> list[StatusMetric]:
        """Get all active experiments for a target."""
        with self._lock:
            return [
                m for m in self._experiments.values() if m.model.target == target
            ]

    def get_status_metric_by_uid(self, uid: str) -> StatusMetric | None:
        """Get a status metric by uid."""
        with self._lock:
            return self._experiments.get(uid)

    def list_uids(self, target: str, action: str) -> set[str]:
        """List all uids matching target and action."""
        with self._lock:
            return {
                uid
                for uid, m in self._experiments.items()
                if m.model.target == target and m.model.action_name == action
            }

    def get_all_uids(self) -> set[str]:
        """Return all registered uids."""
        with self._lock:
            return set(self._experiments.keys())

    def load(self) -> None:
        """Initialize the manager."""
        pass

    def unload(self) -> None:
        """Clear all experiments."""
        with self._lock:
            self._experiments.clear()
