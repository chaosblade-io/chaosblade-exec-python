"""PluginLoader - discovers and loads plugins via setuptools entry_points.

Equivalent to Java's ServiceLoader mechanism for plugin discovery.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.plugin import Plugin

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.center.plugin_manager import PluginBean

logger = logging.getLogger(__name__)

# Entry point group name for ChaosBlade plugins
ENTRY_POINT_GROUP = "chaosblade.plugins"


class PluginLoader:
    """Loads plugins from setuptools entry_points and registers them.

    Plugins are discovered via the 'chaosblade.plugins' entry point group.
    Each entry point should reference a Plugin class or factory function.
    """

    @staticmethod
    def load_plugins() -> int:
        """Discover and register all available plugins.

        Returns:
            Number of plugins successfully loaded.
        """
        plugins = PluginLoader._discover_plugins()
        count = 0

        for plugin in plugins:
            try:
                PluginLoader._register_plugin(plugin)
                count += 1
            except Exception:
                logger.warning(
                    "Failed to register plugin '%s'",
                    getattr(plugin, "get_name", lambda: "unknown")(),
                    exc_info=True,
                )

        logger.info("Loaded %d plugin(s)", count)
        return count

    @staticmethod
    def _discover_plugins() -> list[Plugin]:
        """Discover plugins from entry_points."""
        plugins: list[Plugin] = []

        try:
            # Python 3.9+ has importlib.metadata
            from importlib.metadata import entry_points

            # Python 3.12+ returns SelectableGroups; 3.9-3.11 returns dict
            try:
                eps = entry_points(group=ENTRY_POINT_GROUP)
            except TypeError:
                eps = entry_points().get(ENTRY_POINT_GROUP, [])

            for ep in eps:
                try:
                    plugin_cls = ep.load()
                    # If it's a class, instantiate it
                    if isinstance(plugin_cls, type):
                        plugin = plugin_cls()
                    else:
                        plugin = plugin_cls
                    plugins.append(plugin)
                    logger.debug("Discovered plugin: %s", ep.name)
                except Exception:
                    logger.warning(
                        "Failed to load entry point '%s'", ep.name, exc_info=True
                    )
        except ImportError:
            logger.debug("importlib.metadata not available, skipping entry_points discovery")

        return plugins

    @staticmethod
    def register_plugin(plugin: Plugin) -> None:
        """Manually register a plugin (for programmatic registration)."""
        PluginLoader._register_plugin(plugin)

    @staticmethod
    def _register_plugin(plugin: Plugin) -> None:
        """Register a single plugin with all managers."""
        model_spec = plugin.get_model_spec()
        target = model_spec.get_target()

        # Register model spec
        ManagerFactory.get_model_spec_manager().register_model_spec(model_spec)

        # Create and register plugin bean
        plugin_bean = PluginBean(
            name=plugin.get_name(),
            plugin=plugin,
            point_cut=plugin.get_point_cut(),
            enhancer=plugin.get_enhancer(),
            model_spec=model_spec,
        )
        ManagerFactory.get_plugin_manager().register(target, plugin_bean)

        logger.debug("Registered plugin '%s' for target '%s'", plugin.get_name(), target)
