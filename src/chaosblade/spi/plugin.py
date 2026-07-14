"""Plugin Protocol definition."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.spi.enhancer import BeforeEnhancer, AfterEnhancer
    from chaosblade.spi.model_spec import ModelSpec
    from chaosblade.spi.point_cut import PointCut


@runtime_checkable
class Plugin(Protocol):
    """Plugin interface - the top-level registration unit for a chaos experiment target."""

    def get_name(self) -> str:
        """Return the plugin name."""
        ...

    def get_model_spec(self) -> ModelSpec:
        """Return the model specification for this plugin."""
        ...

    def get_point_cut(self) -> PointCut:
        """Return the point cut (interception point) for this plugin."""
        ...

    def get_enhancer(self) -> BeforeEnhancer | AfterEnhancer:
        """Return the enhancer (before/after advice) for this plugin."""
        ...
