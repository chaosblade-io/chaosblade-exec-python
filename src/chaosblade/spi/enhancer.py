"""BeforeEnhancer and AfterEnhancer base classes."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel

logger = logging.getLogger(__name__)


class BeforeEnhancer(ABC):
    """Base class for before-advice enhancers.

    Implements the template method pattern: checks if active experiments exist
    for the target, then delegates to do_before_advice for model construction.
    """

    def before_advice(
        self,
        target: str,
        method_name: str,
        obj: Any,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """Template method: check experiment existence, build model, inject."""
        from chaosblade.common.center.manager_factory import ManagerFactory
        from chaosblade.common.injection.injector import Injector

        if not ManagerFactory.get_status_manager().exp_exists(target):
            return

        model = self.do_before_advice(target, method_name, obj, args, kwargs)
        if model is None:
            return

        model.target = target
        Injector.inject(model)

    @abstractmethod
    def do_before_advice(
        self,
        target: str,
        method_name: str,
        obj: Any,
        args: tuple,
        kwargs: dict,
    ) -> EnhancerModel | None:
        """Build an EnhancerModel from the method call context.

        Returns None to skip injection for this call.
        """
        ...


class AfterEnhancer(ABC):
    """Base class for after-advice enhancers."""

    @abstractmethod
    def after_advice(
        self,
        target: str,
        method_name: str,
        obj: Any,
        return_value: Any,
    ) -> None:
        """Called after the target method returns."""
        ...
