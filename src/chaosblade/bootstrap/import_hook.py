"""ImportHook - sys.meta_path hook for deferred monkey patching.

Solves the timing problem: when a plugin registers a patch intent before
the target module is imported, this hook will automatically apply the patch
when the module is first imported.

Uses the modern importlib find_spec API (PEP 451) for Python 3.4+.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import logging
import sys
import threading
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Callable, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.bootstrap.patcher import MonkeyPatcher

logger = logging.getLogger(__name__)


@dataclass
class PendingPatch:
    """A patch waiting for its target module to be imported."""

    identifier: str
    module_path: str
    target_attr: str
    target_class: str | None
    wrapper: Callable


class _PostImportLoader(importlib.abc.Loader):
    """A loader wrapper that delegates to the real loader and applies patches after exec."""

    def __init__(self, real_loader: Any, hook: ImportHook, module_path: str) -> None:
        self._real_loader = real_loader
        self._hook = hook
        self._module_path = module_path

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        """Delegate to real loader for module creation."""
        if hasattr(self._real_loader, "create_module"):
            return self._real_loader.create_module(spec)
        return None

    def exec_module(self, module: ModuleType) -> None:
        """Execute module via real loader, then apply pending patches."""
        if hasattr(self._real_loader, "exec_module"):
            self._real_loader.exec_module(module)
        # Apply patches after module is fully loaded
        self._hook._apply_pending(self._module_path)


class ImportHook(importlib.abc.MetaPathFinder):
    """Import hook that auto-applies patches when target modules are imported.

    Uses find_spec (PEP 451) - the modern meta path finder API.

    Usage:
        hook = ImportHook(patcher)
        hook.register_pending("redis-plugin", "redis.client", "execute_command", wrapper, "Redis")
        hook.install()
        # Later, when 'redis.client' is imported, the patch is automatically applied.
    """

    def __init__(self, patcher: MonkeyPatcher) -> None:
        self._patcher = patcher
        self._pending: dict[str, list[PendingPatch]] = {}  # module_path -> [PendingPatch]
        self._lock = threading.Lock()
        self._installed = False

    def register_pending(
        self,
        identifier: str,
        module_path: str,
        target_attr: str,
        wrapper: Callable,
        target_class: str | None = None,
    ) -> None:
        """Register a patch intent that will be applied when the module is imported.

        If the module is already imported, applies immediately.
        """
        # Try immediate application first
        if module_path in sys.modules:
            applied = self._patcher.apply_patch(
                identifier, module_path, target_attr, wrapper, target_class
            )
            if applied:
                logger.debug("Immediate patch applied: %s", identifier)
                return

        # Otherwise queue it
        with self._lock:
            pending = PendingPatch(
                identifier=identifier,
                module_path=module_path,
                target_attr=target_attr,
                target_class=target_class,
                wrapper=wrapper,
            )
            if module_path not in self._pending:
                self._pending[module_path] = []
            self._pending[module_path].append(pending)
            logger.debug(
                "Registered pending patch '%s' for module '%s'",
                identifier,
                module_path,
            )

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """MetaPathFinder.find_spec (PEP 451): intercept imports for modules with pending patches."""
        with self._lock:
            if fullname not in self._pending:
                return None

        # Temporarily remove ourselves to avoid recursion when finding the real spec
        sys.meta_path.remove(self)
        try:
            real_spec = importlib.util.find_spec(fullname)
        finally:
            if self not in sys.meta_path:
                sys.meta_path.insert(0, self)

        if real_spec is None:
            return None

        # Wrap the real loader with our post-import hook
        real_spec.loader = _PostImportLoader(real_spec.loader, self, fullname)
        return real_spec

    def _apply_pending(self, module_path: str) -> None:
        """Apply all pending patches for a module."""
        with self._lock:
            pending_list = self._pending.pop(module_path, [])

        for pending in pending_list:
            try:
                applied = self._patcher.apply_patch(
                    pending.identifier,
                    pending.module_path,
                    pending.target_attr,
                    pending.wrapper,
                    pending.target_class,
                )
                if applied:
                    logger.info(
                        "Deferred patch applied: '%s' on %s",
                        pending.identifier,
                        module_path,
                    )
                else:
                    logger.warning(
                        "Failed to apply deferred patch: '%s'", pending.identifier
                    )
            except Exception:
                logger.warning(
                    "Error applying deferred patch '%s'",
                    pending.identifier,
                    exc_info=True,
                )

    def install(self) -> None:
        """Install this hook into sys.meta_path."""
        if not self._installed:
            sys.meta_path.insert(0, self)
            self._installed = True
            logger.debug("ImportHook installed")

    def uninstall(self) -> None:
        """Remove this hook from sys.meta_path."""
        if self._installed:
            try:
                sys.meta_path.remove(self)
            except ValueError:
                pass
            self._installed = False
            logger.debug("ImportHook uninstalled")

    @property
    def pending_count(self) -> int:
        """Return the number of pending patches."""
        with self._lock:
            return sum(len(v) for v in self._pending.values())
