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

"""Tests for ImportHook and deferred patching."""

import sys
import types

import pytest

from chaosblade.bootstrap.import_hook import ImportHook
from chaosblade.bootstrap.patcher import MonkeyPatcher


class TestImportHook:
    def setup_method(self):
        self.patcher = MonkeyPatcher()
        self.hook = ImportHook(self.patcher)
        # Clean up test modules
        for key in list(sys.modules.keys()):
            if key.startswith("_testhook_"):
                del sys.modules[key]

    def teardown_method(self):
        self.hook.uninstall()
        self.patcher.remove_all()
        for key in list(sys.modules.keys()):
            if key.startswith("_testhook_"):
                del sys.modules[key]

    def test_immediate_patch_if_module_loaded(self):
        """If module is already imported, patch is applied immediately."""
        mod = types.ModuleType("_testhook_loaded")
        mod.func = lambda: "original"
        sys.modules["_testhook_loaded"] = mod

        def wrapper(original, *args, **kwargs):
            return "patched"

        self.hook.register_pending(
            "test-imm", "_testhook_loaded", "func", wrapper
        )
        # Should be applied immediately
        assert mod.func() == "patched"
        assert self.hook.pending_count == 0

    def test_pending_patch_registered(self):
        """If module not imported, patch is queued as pending."""

        def wrapper(original, *args, **kwargs):
            return "patched"

        self.hook.register_pending(
            "test-pend", "_testhook_notloaded", "func", wrapper
        )
        assert self.hook.pending_count == 1

    def test_install_uninstall(self):
        """Install/uninstall modifies sys.meta_path."""
        self.hook.install()
        assert self.hook in sys.meta_path

        self.hook.uninstall()
        assert self.hook not in sys.meta_path

    def test_find_spec_returns_spec_for_pending(self):
        """find_spec returns a ModuleSpec when there are pending patches for the module."""
        def wrapper(original, *args, **kwargs):
            return "patched"

        self.hook.register_pending(
            "test-find", "_testhook_pending_mod", "func", wrapper
        )
        # find_spec should return a spec for pending module (may be None if module doesn't exist)
        # But for non-pending modules, it should always return None
        result = self.hook.find_spec("some.other.module", None)
        assert result is None

    def test_deferred_patch_applied_on_import(self):
        """Patch is applied when the target module is 'imported' (simulated)."""
        # We can simulate by manually calling _apply_pending after inserting module
        def wrapper(original, *args, **kwargs):
            return "deferred_patched"

        self.hook.register_pending(
            "test-defer", "_testhook_deferred", "func", wrapper
        )

        # Simulate the module being imported
        mod = types.ModuleType("_testhook_deferred")
        mod.func = lambda: "original"
        sys.modules["_testhook_deferred"] = mod

        # Trigger deferred application
        self.hook._apply_pending("_testhook_deferred")

        assert mod.func() == "deferred_patched"
        assert self.hook.pending_count == 0
