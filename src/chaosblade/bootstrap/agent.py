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

"""ChaosBladeAgent - main entry point for the ChaosBlade Python executor.

Equivalent to Java's SandboxModule. Coordinates:
- Plugin discovery and registration
- Import hook installation
- HTTP management server startup
- Lifecycle management (start/stop)
"""

from __future__ import annotations

import argparse
import atexit
import logging
import signal
import sys
from http.server import HTTPServer
from typing import TYPE_CHECKING

from chaosblade.bootstrap.enhancer_factory import EnhancerFactory
from chaosblade.bootstrap.import_hook import ImportHook
from chaosblade.bootstrap.patcher import MonkeyPatcher
from chaosblade.bootstrap.plugin_loader import PluginLoader
from chaosblade.common.center.listener_manager import PluginLifecycleListener
from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.center.plugin_manager import PluginBean
from chaosblade.service.server import start_server

logger = logging.getLogger(__name__)


class _PatchLifecycleListener:
    """PluginLifecycleListener implementation that installs/removes patches on plugin load/unload."""

    def __init__(self, patcher: MonkeyPatcher, import_hook: ImportHook) -> None:
        self._patcher = patcher
        self._import_hook = import_hook

    def add(self, plugin_bean: PluginBean) -> None:
        """Install patch for the plugin's point cut."""
        point_cut = plugin_bean.point_cut
        target = plugin_bean.model_spec.get_target()
        enhancer = plugin_bean.enhancer

        # Create wrapper using EnhancerFactory
        wrapper = EnhancerFactory.create_wrapper_for_point_cut(
            target, point_cut, enhancer
        )

        identifier = f"{target}-{point_cut.get_target_module()}-{point_cut.get_target_function()}"

        # Try direct patch first; if module not yet imported, register as pending
        applied = self._patcher.apply_patch(
            identifier=identifier,
            module_path=point_cut.get_target_module(),
            target_attr=point_cut.get_target_function(),
            wrapper=wrapper,
            target_class=point_cut.get_target_class(),
        )
        if not applied:
            # Module not yet imported - register for deferred patching
            self._import_hook.register_pending(
                identifier=identifier,
                module_path=point_cut.get_target_module(),
                target_attr=point_cut.get_target_function(),
                wrapper=wrapper,
                target_class=point_cut.get_target_class(),
            )

    def remove(self, plugin_bean: PluginBean) -> None:
        """Remove patch for the plugin's point cut."""
        point_cut = plugin_bean.point_cut
        target = plugin_bean.model_spec.get_target()
        identifier = f"{target}-{point_cut.get_target_module()}-{point_cut.get_target_function()}"
        self._patcher.remove_patch(identifier)


class ChaosBladeAgent:
    """ChaosBlade Python Agent - coordinates all subsystems.

    Usage:
        agent = ChaosBladeAgent(port=9526)
        agent.start()
        # ... application runs ...
        agent.stop()
    """

    def __init__(self, port: int = 9526, host: str = "127.0.0.1") -> None:
        self._port = port
        self._host = host
        self._server: HTTPServer | None = None
        self._patcher = MonkeyPatcher()
        self._import_hook = ImportHook(self._patcher)
        self._started = False

    @property
    def patcher(self) -> MonkeyPatcher:
        """Access the MonkeyPatcher instance."""
        return self._patcher

    @property
    def import_hook(self) -> ImportHook:
        """Access the ImportHook instance."""
        return self._import_hook

    def start(self) -> None:
        """Start the ChaosBlade agent.

        Steps:
        1. Initialize managers
        2. Install import hook
        3. Set up lifecycle listener
        4. Load plugins (entry_points)
        5. Start HTTP management server
        6. Register signal handlers for graceful shutdown
        """
        if self._started:
            logger.warning("Agent already started")
            return

        logger.info("Starting ChaosBlade Python Agent on %s:%d", self._host, self._port)

        # 1. Initialize managers
        ManagerFactory.load()

        # 2. Install import hook
        self._import_hook.install()

        # 3. Set up lifecycle listener for automatic patch management
        listener = _PatchLifecycleListener(self._patcher, self._import_hook)
        ManagerFactory.get_listener_manager().set_plugin_lifecycle_listener(listener)

        # 4. Load plugins
        plugin_count = PluginLoader.load_plugins()
        logger.info("Loaded %d plugins", plugin_count)

        # 5. Start HTTP server
        self._server = start_server(self._port, self._host)
        actual_port = self._server.server_address[1]

        # 6. Register shutdown hooks
        self._register_shutdown_hooks()

        self._started = True
        logger.info("ChaosBlade Python Agent started successfully on port %d", actual_port)

    def stop(self) -> None:
        """Stop the ChaosBlade agent and clean up all resources."""
        if not self._started:
            return

        logger.info("Stopping ChaosBlade Python Agent")

        # Stop HTTP server
        if self._server:
            self._server.shutdown()
            self._server = None

        # Remove all patches
        removed = self._patcher.remove_all()
        logger.info("Removed %d patches", removed)

        # Uninstall import hook
        self._import_hook.uninstall()

        # Unload managers
        ManagerFactory.unload()

        self._started = False
        logger.info("ChaosBlade Python Agent stopped")

    def _register_shutdown_hooks(self) -> None:
        """Register signal handlers and atexit for graceful shutdown."""
        # atexit ensures cleanup on normal interpreter exit
        atexit.register(self.stop)

        # Handle SIGTERM (docker stop / kill -15)
        def _signal_handler(signum: int, frame: any) -> None:
            logger.info("Received signal %d, shutting down...", signum)
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGTERM, _signal_handler)
        except (OSError, ValueError):
            # May fail if not on main thread
            logger.debug("Could not register SIGTERM handler (not main thread?)")


def main() -> None:
    """CLI entry point for running the agent standalone."""
    parser = argparse.ArgumentParser(description="ChaosBlade Python Agent")
    parser.add_argument("--port", type=int, default=9526, help="HTTP server port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="HTTP server host")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    agent = ChaosBladeAgent(port=args.port, host=args.host)
    agent.start()

    print(f"ChaosBlade Python Agent running on {args.host}:{args.port}")
    print("Press Ctrl+C to stop...")

    try:
        # Block until interrupted
        import threading
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        agent.stop()


if __name__ == "__main__":
    main()
