"""Tests for the built-in fault injection executors."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
)
from chaosblade.common.model.action_model import ActionModel
from chaosblade.common.model.enhancer_model import EnhancerModel
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.common.model.model import Model
from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor
from chaosblade.executor.directly_executors import (
    CpuBurnExecutor,
    MemoryFillExecutor,
)


def _make_enhancer_model(flags: dict[str, str]) -> EnhancerModel:
    """Helper: create an EnhancerModel with action flags already merged."""
    model = Model(target="test", action_name="test")
    for k, v in flags.items():
        model.action.add_flag(k, v)

    em = EnhancerModel()
    em.merge(model)
    return em


# ==========================
# DelayActionExecutor Tests
# ==========================
class TestDelayActionExecutor:
    def test_basic_delay(self):
        """Test basic delay injection (50ms)."""
        executor = DelayActionExecutor()
        em = _make_enhancer_model({"time": "50"})

        start = time.perf_counter()
        executor.run(em)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms >= 45  # Allow some tolerance
        assert elapsed_ms < 200

    def test_delay_with_offset(self):
        """Test delay with offset jitter."""
        executor = DelayActionExecutor()
        em = _make_enhancer_model({"time": "30", "offset": "20"})

        start = time.perf_counter()
        executor.run(em)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should be between 30ms and 50ms (30 + [0,20])
        assert elapsed_ms >= 25
        assert elapsed_ms < 200

    def test_zero_delay(self):
        """Zero delay does nothing."""
        executor = DelayActionExecutor()
        em = _make_enhancer_model({"time": "0"})

        start = time.perf_counter()
        executor.run(em)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50

    def test_missing_time_flag(self):
        """Missing time flag defaults to 0 (no delay)."""
        executor = DelayActionExecutor()
        em = _make_enhancer_model({})

        start = time.perf_counter()
        executor.run(em)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50

    def test_invalid_time_flag(self):
        """Invalid time flag defaults to 0."""
        executor = DelayActionExecutor()
        em = _make_enhancer_model({"time": "not_a_number"})

        start = time.perf_counter()
        executor.run(em)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 50


# ==============================
# ThrowExceptionExecutor Tests
# ==============================
class TestThrowExceptionExecutor:
    def test_throw_runtime_error(self):
        """Throw RuntimeError by name."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({"exception": "RuntimeError", "exception-message": "test error"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.state == ProcessState.THROWS_IMMEDIATELY
        assert isinstance(exc_info.value.exception, RuntimeError)
        assert str(exc_info.value.exception) == "test error"

    def test_throw_value_error(self):
        """Throw ValueError by name."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({"exception": "ValueError", "exception-message": "bad value"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert isinstance(exc_info.value.exception, ValueError)
        assert str(exc_info.value.exception) == "bad value"

    def test_throw_timeout_error(self):
        """Throw TimeoutError."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({"exception": "TimeoutError"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert isinstance(exc_info.value.exception, TimeoutError)

    def test_throw_default_when_no_exception_specified(self):
        """Default to RuntimeError when no exception flag."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert isinstance(exc_info.value.exception, RuntimeError)
        assert "chaosblade" in str(exc_info.value.exception)

    def test_throw_unknown_exception_falls_back(self):
        """Unknown exception class falls back to RuntimeError."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({
            "exception": "NonExistentException",
            "exception-message": "fallback",
        })

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert isinstance(exc_info.value.exception, RuntimeError)

    def test_throw_connection_error(self):
        """Throw ConnectionError."""
        executor = ThrowExceptionExecutor()
        em = _make_enhancer_model({"exception": "ConnectionError", "exception-message": "refused"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert isinstance(exc_info.value.exception, ConnectionError)


# ==============================
# ReturnValueExecutor Tests
# ==============================
class TestReturnValueExecutor:
    def test_return_none(self):
        """Return None."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "null"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.state == ProcessState.RETURN_IMMEDIATELY
        assert exc_info.value.response is None

    def test_return_true(self):
        """Return True."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "true"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response is True

    def test_return_false(self):
        """Return False."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "false"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response is False

    def test_return_integer(self):
        """Return integer."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "42"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response == 42
        assert isinstance(exc_info.value.response, int)

    def test_return_float(self):
        """Return float."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "3.14"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response == 3.14

    def test_return_string(self):
        """Return raw string."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": "hello world"})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response == "hello world"

    def test_return_json_object(self):
        """Return parsed JSON object."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": '{"status": "error", "code": 500}'})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response == {"status": "error", "code": 500}

    def test_return_json_array(self):
        """Return parsed JSON array."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({"return-value": '[1, 2, 3]'})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response == [1, 2, 3]

    def test_return_no_flag_defaults_to_none(self):
        """No return-value flag returns None."""
        executor = ReturnValueExecutor()
        em = _make_enhancer_model({})

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)

        assert exc_info.value.response is None


# ===========================
# DirectlyExecutors Tests
# ===========================
class TestCpuBurnExecutor:
    def test_create_and_destroy(self):
        """Create starts workers, destroy stops them."""
        executor = CpuBurnExecutor()

        model = Model(target="cpu", action_name="cpu")
        model.action.add_flag("cpu-count", "1")
        model.action.add_flag("cpu-percent", "50")

        executor.create_injection("test-uid", model)
        assert len(executor._workers) == 1
        assert executor._running is True

        # Let it run briefly
        time.sleep(0.1)

        executor.destroy_injection("test-uid", model)
        assert executor._running is False
        assert len(executor._workers) == 0


class TestMemoryFillExecutor:
    def test_create_and_destroy_small(self):
        """Allocate and release a small amount of memory."""
        executor = MemoryFillExecutor()

        model = Model(target="mem", action_name="mem")
        model.action.add_flag("mem-size", "1")  # 1MB

        executor.create_injection("test-uid", model)
        # Should have allocated some chunks
        assert len(executor._allocated) > 0

        executor.destroy_injection("test-uid", model)
        assert len(executor._allocated) == 0
