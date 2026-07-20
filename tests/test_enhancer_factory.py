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

"""Tests for the EnhancerFactory."""

import pytest

from chaosblade.bootstrap.enhancer_factory import EnhancerFactory
from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
)


class FakeBeforeEnhancer:
    """Fake before enhancer for testing."""

    def __init__(self, action=None):
        self._action = action
        self.calls = []

    def before_advice(self, target, method_name, obj, args, kwargs):
        self.calls.append((target, method_name, obj, args, kwargs))
        if self._action:
            self._action()


class FakeAfterEnhancer:
    """Fake after enhancer for testing."""

    def __init__(self):
        self.calls = []

    def after_advice(self, target, method_name, obj, result):
        self.calls.append((target, method_name, obj, result))


class TestEnhancerFactory:
    def test_normal_passthrough(self):
        """Wrapper calls original function when no exception."""
        enhancer = FakeBeforeEnhancer()
        wrapper = EnhancerFactory.create_before_wrapper("redis", enhancer)

        def original(x, y):
            return x + y

        result = wrapper(original, 3, 4)
        assert result == 7
        assert len(enhancer.calls) == 1

    def test_return_immediately(self):
        """Wrapper returns response when RETURN_IMMEDIATELY is raised."""

        def raise_return():
            raise InterruptProcessException(
                state=ProcessState.RETURN_IMMEDIATELY, response="cached_value"
            )

        enhancer = FakeBeforeEnhancer(action=raise_return)
        wrapper = EnhancerFactory.create_before_wrapper("redis", enhancer)

        def original():
            return "should_not_be_called"

        result = wrapper(original)
        assert result == "cached_value"

    def test_throws_immediately(self):
        """Wrapper raises exception when THROWS_IMMEDIATELY is raised."""

        def raise_throw():
            raise InterruptProcessException(
                state=ProcessState.THROWS_IMMEDIATELY,
                exception=RuntimeError("injected fault"),
            )

        enhancer = FakeBeforeEnhancer(action=raise_throw)
        wrapper = EnhancerFactory.create_before_wrapper("redis", enhancer)

        def original():
            return "ok"

        with pytest.raises(RuntimeError, match="injected fault"):
            wrapper(original)

    def test_enhancer_error_does_not_break_original(self):
        """If enhancer raises a non-Interrupt exception, original still executes."""

        def raise_error():
            raise ValueError("internal enhancer bug")

        enhancer = FakeBeforeEnhancer(action=raise_error)
        wrapper = EnhancerFactory.create_before_wrapper("redis", enhancer)

        def original():
            return "ok"

        result = wrapper(original)
        assert result == "ok"

    def test_after_enhancer_called(self):
        """After enhancer receives the return value."""
        before = FakeBeforeEnhancer()
        after = FakeAfterEnhancer()
        wrapper = EnhancerFactory.create_before_wrapper("redis", before, after)

        def original(x):
            return x * 2

        result = wrapper(original, 5)
        assert result == 10
        assert len(after.calls) == 1
        assert after.calls[0][3] == 10  # result

    def test_after_enhancer_not_called_on_interrupt(self):
        """After enhancer is NOT called when before raises interrupt."""

        def raise_return():
            raise InterruptProcessException(
                state=ProcessState.RETURN_IMMEDIATELY, response="short_circuit"
            )

        before = FakeBeforeEnhancer(action=raise_return)
        after = FakeAfterEnhancer()
        wrapper = EnhancerFactory.create_before_wrapper("redis", before, after)

        def original():
            return "original"

        result = wrapper(original)
        assert result == "short_circuit"
        assert len(after.calls) == 0


class TestAsyncEnhancerFactory:
    @pytest.mark.asyncio
    async def test_async_normal_passthrough(self):
        """Async wrapper calls original coroutine."""
        enhancer = FakeBeforeEnhancer()
        wrapper = EnhancerFactory.create_async_before_wrapper("redis", enhancer)

        async def original(x):
            return x * 3

        result = await wrapper(original, 5)
        assert result == 15

    @pytest.mark.asyncio
    async def test_async_return_immediately(self):
        """Async wrapper returns cached value on interrupt."""

        def raise_return():
            raise InterruptProcessException(
                state=ProcessState.RETURN_IMMEDIATELY, response="async_cached"
            )

        enhancer = FakeBeforeEnhancer(action=raise_return)
        wrapper = EnhancerFactory.create_async_before_wrapper("redis", enhancer)

        async def original():
            return "should_not_run"

        result = await wrapper(original)
        assert result == "async_cached"
