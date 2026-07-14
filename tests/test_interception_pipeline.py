"""Integration tests for the full interception pipeline.

Tests the complete flow:
  Plugin → PluginLoader → LifecycleListener → Patcher → EnhancerFactory → Injector
"""

import sys
import types
from typing import Any

import pytest

from chaosblade.bootstrap.enhancer_factory import EnhancerFactory
from chaosblade.bootstrap.patcher import MonkeyPatcher
from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
)
from chaosblade.common.model.enhancer_model import EnhancerModel
from chaosblade.common.injection.injector import Injector
from chaosblade.spi.enhancer import BeforeEnhancer


class TestInterceptionPipeline:
    """Test the full pipeline from patching a function to fault injection."""

    def setup_method(self):
        """Set up a clean environment."""
        for key in list(sys.modules.keys()):
            if key.startswith("_test_pipeline_"):
                del sys.modules[key]

    def teardown_method(self):
        for key in list(sys.modules.keys()):
            if key.startswith("_test_pipeline_"):
                del sys.modules[key]

    def test_full_interception_with_delay_injection(self):
        """Simulate a delay injection through the full pipeline.

        1. Patch a target function
        2. Create an experiment
        3. Call the patched function → before_advice → Injector → interrupt
        """
        import time

        # Create a target module with a function to patch
        mod = types.ModuleType("_test_pipeline_target")
        mod.slow_call = lambda: "fast_result"
        sys.modules["_test_pipeline_target"] = mod

        # Create the before_enhancer that simulates what a real plugin would do
        class DelayEnhancer(BeforeEnhancer):
            def __init__(self):
                self.intercepted = False

            def get_target(self) -> str:
                return "test"

            def do_before_advice(self, target, method_name, obj, args, kwargs) -> EnhancerModel:
                # Not used in this simplified test
                pass

            def before_advice(self, target, method_name, obj, args, kwargs):
                self.intercepted = True
                # Simulate what the injector would do: throw InterruptProcessException
                raise InterruptProcessException(
                    state=ProcessState.RETURN_IMMEDIATELY,
                    response="delayed_result",
                )

        enhancer = DelayEnhancer()

        # Create the wrapper using EnhancerFactory
        wrapper = EnhancerFactory.create_before_wrapper("test", enhancer)

        # Apply the patch
        patcher = MonkeyPatcher()
        applied = patcher.apply_patch(
            "test-delay", "_test_pipeline_target", "slow_call", wrapper
        )
        assert applied is True

        # Call the patched function - should be intercepted
        result = mod.slow_call()
        assert result == "delayed_result"
        assert enhancer.intercepted is True

        # Remove patch - should restore original
        patcher.remove_patch("test-delay")
        result = mod.slow_call()
        assert result == "fast_result"

    def test_multiple_patches_on_same_module(self):
        """Multiple patches on different functions in the same module."""
        mod = types.ModuleType("_test_pipeline_multi")
        mod.func_a = lambda: "a"
        mod.func_b = lambda: "b"
        sys.modules["_test_pipeline_multi"] = mod

        patcher = MonkeyPatcher()

        def wrapper_a(original, *args, **kwargs):
            return "patched_a"

        def wrapper_b(original, *args, **kwargs):
            return "patched_b"

        patcher.apply_patch("pa", "_test_pipeline_multi", "func_a", wrapper_a)
        patcher.apply_patch("pb", "_test_pipeline_multi", "func_b", wrapper_b)

        assert mod.func_a() == "patched_a"
        assert mod.func_b() == "patched_b"
        assert patcher.get_patch_count() == 2

        # Remove only one
        patcher.remove_patch("pa")
        assert mod.func_a() == "a"
        assert mod.func_b() == "patched_b"

        patcher.remove_all()
