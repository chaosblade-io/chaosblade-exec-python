"""Tests for ModelSpecManager and BaseModelSpec."""

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult
from chaosblade.common.model.action_model import ActionModel


# --- Test helpers ---

class FakeActionSpec:
    """Minimal ActionSpec implementation for testing."""

    def __init__(self, name, aliases=None):
        self._name = name
        self._aliases = aliases or []

    def get_name(self):
        return self._name

    def get_aliases(self):
        return self._aliases

    def get_short_desc(self):
        return ""

    def get_long_desc(self):
        return ""

    def get_action_flags(self):
        return []

    def predicate(self, action_model):
        return PredicateResult.ok()

    def get_action_executor(self):
        return None


class FakeModelSpec(BaseModelSpec):
    """Minimal BaseModelSpec implementation for testing."""

    def get_target(self):
        return "redis"

    def get_short_desc(self):
        return "Redis"

    def get_long_desc(self):
        return "Redis plugin"

    def get_matcher_specs(self):
        return []


# --- Tests ---

class TestBaseModelSpec:
    def test_add_and_get_action_spec(self):
        spec = FakeModelSpec()
        spec.add_action_spec(FakeActionSpec("delay"))
        assert spec.get_action_spec("delay") is not None
        assert spec.get_action_spec("nonexist") is None

    def test_alias_lookup(self):
        spec = FakeModelSpec()
        spec.add_action_spec(FakeActionSpec("modifyCode", aliases=["mc"]))
        assert spec.get_action_spec("mc") is not None
        assert spec.get_action_spec("modifyCode") is not None
        assert spec.get_action_spec("MC") is None  # Aliases are case-sensitive

    def test_get_actions_list(self):
        spec = FakeModelSpec()
        spec.add_action_spec(FakeActionSpec("delay"))
        spec.add_action_spec(FakeActionSpec("exception"))
        actions = spec.get_actions()
        assert len(actions) == 2

    def test_predicate_action_not_found(self):
        spec = FakeModelSpec()
        spec.add_action_spec(FakeActionSpec("delay"))
        model = Model("redis", "nonexist")
        result = spec.predicate(model)
        assert result.success is False
        assert "not supported" in result.error

    def test_predicate_success(self):
        spec = FakeModelSpec()
        spec.add_action_spec(FakeActionSpec("delay"))
        model = Model("redis", "delay")
        result = spec.predicate(model)
        assert result.success is True


class TestModelSpecManager:
    def test_register_and_get(self):
        msm = ManagerFactory.get_model_spec_manager()
        spec = FakeModelSpec()
        msm.register_model_spec(spec)
        assert msm.get_model_spec("redis") is spec
        assert msm.get_model_spec("flask") is None

    def test_list_all(self):
        msm = ManagerFactory.get_model_spec_manager()
        msm.register_model_spec(FakeModelSpec())
        assert len(msm.list_all()) == 1

    def test_unload(self):
        msm = ManagerFactory.get_model_spec_manager()
        msm.register_model_spec(FakeModelSpec())
        msm.unload()
        assert msm.get_model_spec("redis") is None
