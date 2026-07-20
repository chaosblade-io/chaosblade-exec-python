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

"""ManagerFactory - global singleton factory for all managers."""

from __future__ import annotations

from chaosblade.common.center.status_manager import DefaultStatusManager
from chaosblade.common.center.model_spec_manager import DefaultModelSpecManager
from chaosblade.common.center.plugin_manager import DefaultPluginManager
from chaosblade.common.center.listener_manager import DefaultListenerManager


class ManagerFactory:
    """Global factory providing access to all manager singletons.

    Usage:
        ManagerFactory.get_status_manager().register_exp(uid, model)
        ManagerFactory.load()   # Initialize all managers
        ManagerFactory.unload() # Clean up all managers
    """

    _status_manager = DefaultStatusManager()
    _model_spec_manager = DefaultModelSpecManager()
    _plugin_manager = DefaultPluginManager()
    _listener_manager = DefaultListenerManager()

    @classmethod
    def get_status_manager(cls) -> DefaultStatusManager:
        """Get the status manager instance."""
        return cls._status_manager

    @classmethod
    def get_model_spec_manager(cls) -> DefaultModelSpecManager:
        """Get the model spec manager instance."""
        return cls._model_spec_manager

    @classmethod
    def get_plugin_manager(cls) -> DefaultPluginManager:
        """Get the plugin manager instance."""
        return cls._plugin_manager

    @classmethod
    def get_listener_manager(cls) -> DefaultListenerManager:
        """Get the listener manager instance."""
        return cls._listener_manager

    @classmethod
    def load(cls) -> None:
        """Initialize all managers."""
        cls._model_spec_manager.load()
        cls._listener_manager.load()
        cls._status_manager.load()

    @classmethod
    def unload(cls) -> None:
        """Clean up all managers and reset state."""
        cls._status_manager.unload()
        cls._model_spec_manager.unload()
        cls._plugin_manager.unload()
        cls._listener_manager.unload()
