"""Tests for data model classes and package-level exports."""

import pytest

from chaosblade.common.model.action_model import ActionModel
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult


class TestPredicateResult:
    def test_ok(self):
        result = PredicateResult.ok()
        assert result.success is True
        assert result.error == ""

    def test_fail(self):
        result = PredicateResult.fail("something wrong")
        assert result.success is False
        assert result.error == "something wrong"

    def test_frozen(self):
        result = PredicateResult.ok()
        try:
            result.success = False  # type: ignore
            assert False, "Should raise"
        except Exception:
            pass


class TestActionModel:
    def test_name(self):
        action = ActionModel("delay")
        assert action.name == "delay"

    def test_flags(self):
        action = ActionModel("delay")
        action.add_flag("time", "3000")
        action.add_flag("offset", "500")
        assert action.get_flag("time") == "3000"
        assert action.get_flag("offset") == "500"
        assert action.get_flag("nonexist") is None

    def test_flags_copy(self):
        action = ActionModel("delay")
        action.add_flag("time", "3000")
        flags = action.flags
        flags["time"] = "9999"
        assert action.get_flag("time") == "3000"  # Original unchanged


class TestMatcherModel:
    def test_add_get(self):
        matcher = MatcherModel()
        matcher.add("key", "user:*")
        assert matcher.get("key") == "user:*"
        assert matcher.get("nonexist") is None

    def test_bool(self):
        matcher = MatcherModel()
        assert not matcher
        matcher.add("key", "value")
        assert matcher

    def test_matchers_property(self):
        matcher = MatcherModel()
        matcher.add("a", "1")
        matcher.add("b", "2")
        assert matcher.matchers == {"a": "1", "b": "2"}


class TestModel:
    def test_basic(self):
        model = Model("redis", "delay")
        assert model.target == "redis"
        assert model.action_name == "delay"
        assert model.action.name == "delay"
        assert not model.matcher

    def test_matcher_setter(self):
        model = Model("redis", "delay")
        matcher = MatcherModel()
        matcher.add("key", "user:*")
        model.matcher = matcher
        assert model.matcher.get("key") == "user:*"

    def test_repr(self):
        model = Model("redis", "delay")
        model.matcher.add("cmd", "GET")
        s = repr(model)
        assert "redis" in s
        assert "delay" in s


class TestInitExports:
    """Test that top-level __init__.py exports work."""

    def test_import_agent(self):
        from chaosblade import ChaosBladeAgent
        assert ChaosBladeAgent is not None

    def test_import_model(self):
        from chaosblade import Model
        m = Model("test", "delay")
        assert m.target == "test"

    def test_import_enhancer_model(self):
        from chaosblade import EnhancerModel
        em = EnhancerModel()
        assert em.target == ""

    def test_import_injector(self):
        from chaosblade import Injector
        assert hasattr(Injector, "inject")

    def test_version(self):
        import re
        import chaosblade
        assert isinstance(chaosblade.__version__, str)
        assert re.match(r"^\d+\.\d+\.\d+", chaosblade.__version__)

    def test_invalid_attr_raises(self):
        import chaosblade
        with pytest.raises(AttributeError):
            _ = chaosblade.NonExistentThing
