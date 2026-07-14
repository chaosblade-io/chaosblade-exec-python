"""Tests for the MonkeyPatcher engine."""

import sys
import types

from chaosblade.bootstrap.patcher import MonkeyPatcher


def _create_test_module(name: str) -> types.ModuleType:
    """Create and register a fake module for testing."""
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


class TestMonkeyPatcher:
    def setup_method(self):
        self.patcher = MonkeyPatcher()
        # Clean up any test modules from previous tests
        for key in list(sys.modules.keys()):
            if key.startswith("_test_mod_"):
                del sys.modules[key]

    def teardown_method(self):
        self.patcher.remove_all()
        for key in list(sys.modules.keys()):
            if key.startswith("_test_mod_"):
                del sys.modules[key]

    def test_apply_patch_module_function(self):
        """Patch a module-level function."""
        mod = _create_test_module("_test_mod_1")
        mod.greet = lambda name: f"hello {name}"

        def wrapper(original, *args, **kwargs):
            return f"wrapped: {original(*args, **kwargs)}"

        assert self.patcher.apply_patch("test1", "_test_mod_1", "greet", wrapper)
        assert mod.greet("world") == "wrapped: hello world"

    def test_apply_patch_class_method(self):
        """Patch a class method."""
        mod = _create_test_module("_test_mod_2")

        class MyClass:
            def do_work(self, x):
                return x * 2

        mod.MyClass = MyClass

        def wrapper(original, *args, **kwargs):
            result = original(*args, **kwargs)
            return result + 100

        assert self.patcher.apply_patch(
            "test2", "_test_mod_2", "do_work", wrapper, target_class="MyClass"
        )
        obj = MyClass()
        assert obj.do_work(5) == 110  # 5*2 + 100

    def test_remove_patch(self):
        """Remove a patch restores original behavior."""
        mod = _create_test_module("_test_mod_3")
        mod.add = lambda a, b: a + b

        def wrapper(original, *args, **kwargs):
            return -1

        self.patcher.apply_patch("test3", "_test_mod_3", "add", wrapper)
        assert mod.add(1, 2) == -1

        self.patcher.remove_patch("test3")
        assert mod.add(1, 2) == 3

    def test_module_not_imported(self):
        """Cannot patch a module that's not imported."""
        def wrapper(original, *args, **kwargs):
            return None

        assert self.patcher.apply_patch(
            "test4", "_nonexistent_module_xyz_", "func", wrapper
        ) is False

    def test_duplicate_patch(self):
        """Cannot apply same identifier twice."""
        mod = _create_test_module("_test_mod_5")
        mod.func = lambda: 1

        def wrapper(original, *args, **kwargs):
            return 2

        assert self.patcher.apply_patch("test5", "_test_mod_5", "func", wrapper) is True
        assert self.patcher.apply_patch("test5", "_test_mod_5", "func", wrapper) is False

    def test_remove_all(self):
        """remove_all removes all patches."""
        mod = _create_test_module("_test_mod_6")
        mod.f1 = lambda: "a"
        mod.f2 = lambda: "b"

        def w(original, *args, **kwargs):
            return "patched"

        self.patcher.apply_patch("p1", "_test_mod_6", "f1", w)
        self.patcher.apply_patch("p2", "_test_mod_6", "f2", w)
        assert self.patcher.get_patch_count() == 2

        removed = self.patcher.remove_all()
        assert removed == 2
        assert mod.f1() == "a"
        assert mod.f2() == "b"

    def test_is_patched(self):
        mod = _create_test_module("_test_mod_7")
        mod.func = lambda: 1

        def w(original, *args, **kwargs):
            return 2

        assert not self.patcher.is_patched("test7")
        self.patcher.apply_patch("test7", "_test_mod_7", "func", w)
        assert self.patcher.is_patched("test7")

    def test_preserves_metadata(self):
        """Patched function preserves original name and has __wrapped__."""
        mod = _create_test_module("_test_mod_8")

        def original_func():
            """Original docstring."""
            return 42

        mod.original_func = original_func

        def wrapper(original, *args, **kwargs):
            return original(*args, **kwargs)

        self.patcher.apply_patch("test8", "_test_mod_8", "original_func", wrapper)
        assert mod.original_func.__name__ == "original_func"
        assert mod.original_func.__wrapped__ is original_func

    def test_async_function(self):
        """Patch an async function."""
        import asyncio

        mod = _create_test_module("_test_mod_9")

        async def async_greet(name):
            return f"hello {name}"

        mod.async_greet = async_greet

        def wrapper(original, *args, **kwargs):
            # For async, wrapper receives the coroutine-returning function
            # MonkeyPatcher creates an async wrapper automatically
            return f"wrapped"

        # MonkeyPatcher detects async and wraps accordingly
        self.patcher.apply_patch("test9", "_test_mod_9", "async_greet", wrapper)
        # The patched function should be awaitable
        import inspect
        assert inspect.iscoroutinefunction(mod.async_greet)
