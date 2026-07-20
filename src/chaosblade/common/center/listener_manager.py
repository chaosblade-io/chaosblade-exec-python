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
