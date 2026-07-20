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

"""MonkeyPatcher - core patching engine replacing JVM Sandbox's event watcher.

Provides apply_patch/remove_patch for intercepting Python functions/methods
at runtime. Supports both sync and async functions.
"""

from __future__ import annotations

import inspect
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class PatchRecord:
    """Record of an applied patch for later removal."""

    identifier: str
    module_path: str
    target_attr: str
    target_class: str | None
    original: Any
    patched: Any


class MonkeyPatcher:
    """Engine for applying and removing monkey patches on Python functions/methods.

    Replaces JVM Sandbox's moduleEventWatcher.watch/delete mechanism.
    Thread-safe via internal lock.
    """

    def __init__(self) -> None:
        self._patches: dict[str, PatchRecord] = {}  # identifier -> PatchRecord
        self._lock = threading.Lock()

    def apply_patch(
        self,
        identifier: str,
        module_path: str,
        target_attr: str,
        wrapper: Callable,
        target_class: str | None = None,
    ) -> bool:
        """Apply a monkey patch to a module function or class method.

        Args:
            identifier: Unique patch identifier (e.g., "redis-plugin")
            module_path: Module path (e.g., "redis.client")
            target_attr: Function/method name (e.g., "execute_command")
            wrapper: Wrapper function that takes (original_func, *args, **kwargs)
            target_class: Optional class name (e.g., "Redis")

        Returns:
            True if patch was applied, False if module not yet imported or already patched.
        """
        import sys

        with self._lock:
            if identifier in self._patches:
                logger.debug("Patch '%s' already applied, skipping", identifier)
                return False

            # Get the module
            module = sys.modules.get(module_path)
            if module is None:
                logger.debug("Module '%s' not yet imported, cannot patch", module_path)
                return False

            # Get the target (class or module)
            if target_class:
                target_obj = getattr(module, target_class, None)
                if target_obj is None:
                    logger.warning(
                        "Class '%s' not found in module '%s'", target_class, module_path
                    )
                    return False
            else:
                target_obj = module

            # Get the original function
            original = getattr(target_obj, target_attr, None)
            if original is None:
                logger.warning(
                    "Attribute '%s' not found on '%s'", target_attr, target_obj
                )
                return False

            # Create the patched function
            patched = self._create_wrapper(original, wrapper)

            # Apply the patch
            setattr(target_obj, target_attr, patched)

            # Record for removal
            self._patches[identifier] = PatchRecord(
                identifier=identifier,
                module_path=module_path,
                target_attr=target_attr,
                target_class=target_class,
                original=original,
                patched=patched,
            )

            logger.info(
                "Applied patch '%s' on %s.%s%s",
                identifier,
                module_path,
                f"{target_class}." if target_class else "",
                target_attr,
            )
            return True

    def remove_patch(self, identifier: str) -> bool:
        """Remove a previously applied patch.

        Args:
            identifier: The patch identifier used in apply_patch.

        Returns:
            True if patch was removed, False if not found.
        """
        import sys

        with self._lock:
            record = self._patches.pop(identifier, None)
            if record is None:
                logger.debug("Patch '%s' not found, nothing to remove", identifier)
                return False

            # Get the target
            module = sys.modules.get(record.module_path)
            if module is None:
                logger.warning(
                    "Module '%s' no longer imported, cannot restore", record.module_path
                )
                return False

            if record.target_class:
                target_obj = getattr(module, record.target_class, None)
            else:
                target_obj = module

            if target_obj is None:
                return False

            # Restore original
            setattr(target_obj, record.target_attr, record.original)

            logger.info("Removed patch '%s'", identifier)
            return True

    def remove_all(self) -> int:
        """Remove all applied patches.

        Returns:
            Number of patches removed.
        """
        # Get identifiers while locked
        with self._lock:
            identifiers = list(self._patches.keys())

        count = 0
        for ident in identifiers:
            if self.remove_patch(ident):
                count += 1
        return count

    def is_patched(self, identifier: str) -> bool:
        """Check if a patch is currently applied."""
        with self._lock:
            return identifier in self._patches

    def get_patch_count(self) -> int:
        """Return the number of active patches."""
        with self._lock:
            return len(self._patches)

    def _create_wrapper(self, original: Any, wrapper: Callable) -> Callable:
        """Create a wrapper function that handles both sync and async targets."""
        if inspect.iscoroutinefunction(original):
            # Async wrapper
            async def async_patched(*args: Any, **kwargs: Any) -> Any:
                return await wrapper(original, *args, **kwargs)

            # Preserve metadata
            async_patched.__name__ = getattr(original, "__name__", "unknown")
            async_patched.__qualname__ = getattr(original, "__qualname__", "unknown")
            async_patched.__module__ = getattr(original, "__module__", "")
            async_patched.__doc__ = getattr(original, "__doc__", None)
            async_patched.__wrapped__ = original
            return async_patched
        else:
            # Sync wrapper
            def sync_patched(*args: Any, **kwargs: Any) -> Any:
                return wrapper(original, *args, **kwargs)

            # Preserve metadata
            sync_patched.__name__ = getattr(original, "__name__", "unknown")
            sync_patched.__qualname__ = getattr(original, "__qualname__", "unknown")
            sync_patched.__module__ = getattr(original, "__module__", "")
            sync_patched.__doc__ = getattr(original, "__doc__", None)
            sync_patched.__wrapped__ = original
            return sync_patched
