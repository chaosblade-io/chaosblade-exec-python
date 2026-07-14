"""PluginManager - manages plugin registrations and lazy loading state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.enhancer import BeforeEnhancer, AfterEnhancer
    from chaosblade.spi.model_spec import ModelSpec
    from chaosblade.spi.point_cut import PointCut
    from chaosblade.spi.plugin import Plugin


@dataclass
class PluginBean:
    """Wrapper for a registered plugin instance."""

    name: str
    plugin: Plugin
    point_cut: PointCut
    enhancer: BeforeEnhancer | AfterEnhancer
    model_spec: ModelSpec


@dataclass
class PluginBeans:
    """Collection of plugin beans for a target, with load state tracking."""

    plugin_beans: list[PluginBean] = field(default_factory=list)
    loaded: bool = False


class DefaultPluginManager:
    """Manages plugin registrations indexed by target name."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginBeans] = {}

    def register(self, target: str, plugin_bean: PluginBean) -> None:
        """Register a plugin bean for a target."""
        if target not in self._plugins:
            self._plugins[target] = PluginBeans()
        self._plugins[target].plugin_beans.append(plugin_bean)

    def get_plugins(self, target: str) -> PluginBeans | None:
        """Get all plugin beans for a target."""
        return self._plugins.get(target)

    def set_load(self, plugin_beans: PluginBeans, target: str) -> None:
        """Mark a target's plugins as loaded."""
        plugin_beans.loaded = True

    def load(self) -> None:
        """Initialize the manager."""
        pass

    def unload(self) -> None:
        """Clear all registrations."""
        self._plugins.clear()
