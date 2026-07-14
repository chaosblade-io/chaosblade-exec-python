"""ListenerManager - manages plugin lifecycle listeners."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from chaosblade.common.center.plugin_manager import PluginBean


@runtime_checkable
class PluginLifecycleListener(Protocol):
    """Listener for plugin lifecycle events (load/unload)."""

    def add(self, plugin_bean: PluginBean) -> None:
        """Called when a plugin is loaded/activated."""
        ...

    def remove(self, plugin_bean: PluginBean) -> None:
        """Called when a plugin is unloaded/deactivated."""
        ...


class DefaultListenerManager:
    """Manages the plugin lifecycle listener singleton."""

    def __init__(self) -> None:
        self._listener: PluginLifecycleListener | None = None

    def get_plugin_lifecycle_listener(self) -> PluginLifecycleListener | None:
        """Get the registered listener."""
        return self._listener

    def set_plugin_lifecycle_listener(self, listener: PluginLifecycleListener) -> None:
        """Set the plugin lifecycle listener."""
        self._listener = listener

    def load(self) -> None:
        """Initialize the manager."""
        pass

    def unload(self) -> None:
        """Clear the listener."""
        self._listener = None
