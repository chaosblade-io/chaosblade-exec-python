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

"""Tests for the core Injector."""

import pytest

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
    throw_return_immediately,
)
from chaosblade.common.injection.injector import Injector
from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.common.model.enhancer_model import EnhancerModel
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult


# --- Test helpers ---

class FakeExecutor:
    """Tracks whether run() was called and with what model."""

    def __init__(self, raise_interrupt=False):
        self.called = False
        self.last_model = None
        self._raise_interrupt = raise_interrupt

    def run(self, enhancer_model):
        self.called = True
        self.last_model = enhancer_model
        if self._raise_interrupt:
            throw_return_immediately("injected_value")


class FailingExecutor:
    """Executor that raises a generic exception."""

    def run(self, enhancer_model):
        raise RuntimeError("executor failed")


class FakeActionSpec:
    def __init__(self, name, executor):
        self._name = name
        self._executor = executor

    def get_name(self):
        return self._name

    def get_aliases(self):
        return []

    def get_short_desc(self):
        return ""

    def get_long_desc(self):
        return ""

    def get_action_flags(self):
        return []

    def predicate(self, action_model):
        return PredicateResult.ok()

    def get_action_executor(self):
        return self._executor


class FakeModelSpec(BaseModelSpec):
    def __init__(self, target="redis"):
        super().__init__()
        self._target = target

    def get_target(self):
        return self._target

    def get_short_desc(self):
        return ""

    def get_long_desc(self):
        return ""

    def get_matcher_specs(self):
        return []


def _setup_experiment(target, action, matchers=None, executor=None):
    """Helper to register a model spec and experiment."""
    if executor is None:
        executor = FakeExecutor()
    spec = FakeModelSpec(target)
    spec.add_action_spec(FakeActionSpec(action, executor))
    ManagerFactory.get_model_spec_manager().register_model_spec(spec)

    model = Model(target, action)
    if matchers:
        for k, v in matchers.items():
            model.matcher.add(k, v)
    ManagerFactory.get_status_manager().register_exp("uid1", model)
    return executor


# --- Tests ---

class TestInjectorCompare:
    def test_empty_matchers_match_all(self):
        """No matchers on experiment -> matches any request."""
        executor = _setup_experiment("redis", "delay")

        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True

    def test_exact_match(self):
        """Exact matcher value matches."""
        executor = _setup_experiment("redis", "delay", {"cmd": "GET"})

        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True

    def test_exact_match_case_insensitive(self):
        """Matching is case-insensitive."""
        executor = _setup_experiment("redis", "delay", {"cmd": "get"})

        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True

    def test_no_match(self):
        """Matcher value mismatch -> no injection."""
        executor = _setup_experiment("redis", "delay", {"cmd": "GET"})

        mm = MatcherModel()
        mm.add("cmd", "SET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is False

    def test_regex_match(self):
        """Key ending with -regex uses regex matching."""
        executor = _setup_experiment("redis", "delay", {"cmd-regex": "GET|SET"})

        mm = MatcherModel()
        mm.add("cmd-regex", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True

    def test_missing_actual_value(self):
        """If enhancer model lacks a required matcher key -> no match."""
        executor = _setup_experiment("redis", "delay", {"cmd": "GET"})

        mm = MatcherModel()  # No "cmd" key
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is False

    def test_skips_effect_count(self):
        """effect-count matcher is skipped during comparison."""
        executor = _setup_experiment(
            "redis", "delay", {"cmd": "GET", "effect-count": "5"}
        )

        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True


class TestInjectorLimitAndIncrease:
    def test_effect_count_limit(self):
        """After reaching effect-count limit, injection stops."""
        executor = _setup_experiment(
            "redis", "delay", {"effect-count": "2"}
        )

        for _ in range(3):
            mm = MatcherModel()
            em = EnhancerModel(matcher_model=mm)
            em.target = "redis"
            try:
                Injector.inject(em)
            except InterruptProcessException:
                pass

        # Should have been called only twice
        metric = ManagerFactory.get_status_manager().get_status_metric_by_uid("uid1")
        assert metric.count == 2

    def test_effect_percent_zero(self):
        """effect-percent=0 means never inject."""
        executor = _setup_experiment(
            "redis", "delay", {"effect-percent": "0"}
        )

        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is False


class TestInjectorFullFlow:
    def test_interrupt_process_propagates(self):
        """InterruptProcessException is propagated to caller."""
        _setup_experiment("redis", "delay", executor=FakeExecutor(raise_interrupt=True))

        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        with pytest.raises(InterruptProcessException) as exc_info:
            Injector.inject(em)
        assert exc_info.value.state == ProcessState.RETURN_IMMEDIATELY
        assert exc_info.value.response == "injected_value"

    def test_executor_failure_decreases_count(self):
        """If executor raises non-interrupt exception, count is decreased."""
        _setup_experiment("redis", "delay", executor=FailingExecutor())

        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        # Should not raise
        Injector.inject(em)

        metric = ManagerFactory.get_status_manager().get_status_metric_by_uid("uid1")
        assert metric.count == 0  # increased then decreased

    def test_merge_sets_action_flags(self):
        """After inject, enhancer_model has merged action flags."""
        executor = _setup_experiment("redis", "delay")

        # Add flags to experiment model
        metric = ManagerFactory.get_status_manager().get_status_metric_by_uid("uid1")
        metric.model.action.add_flag("time", "3000")

        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)
        assert executor.called is True
        assert em.get_action_flag("time") == "3000"

    def test_no_experiment_no_injection(self):
        """If no experiments registered for target, nothing happens."""
        spec = FakeModelSpec("redis")
        spec.add_action_spec(FakeActionSpec("delay", FakeExecutor()))
        ManagerFactory.get_model_spec_manager().register_model_spec(spec)
        # No experiment registered

        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"

        Injector.inject(em)  # Should not raise
