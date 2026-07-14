"""Tests for EnhancerModel."""

from chaosblade.common.model.enhancer_model import EnhancerModel
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.common.model.model import Model


class TestEnhancerModel:
    def test_basic_creation(self):
        em = EnhancerModel()
        assert em.target == ""
        assert em.matcher_model is not None
        assert em.action_model is None

    def test_with_matcher_model(self):
        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        assert em.matcher_model.get("cmd") == "GET"

    def test_merge(self):
        model = Model("redis", "delay")
        model.action.add_flag("time", "3000")

        em = EnhancerModel()
        em.merge(model)
        assert em.get_action_flag("time") == "3000"
        assert em.action_model is not None
        assert em.action_model.name == "delay"

    def test_get_action_flag_before_merge(self):
        em = EnhancerModel()
        assert em.get_action_flag("time") is None

    def test_custom_matcher(self):
        class FakeMatcher:
            def match(self, rule_value, actual_value):
                return rule_value in actual_value

            def regex_match(self, pattern, actual_value):
                return False

        em = EnhancerModel()
        em.add_custom_matcher("querystring", "foo=bar&baz=1", FakeMatcher())
        assert em.matcher_model.get("querystring") == "foo=bar&baz=1"
        assert em.get_matcher("querystring") is not None
        assert em.get_matcher("nonexist") is None

    def test_method_context(self):
        em = EnhancerModel()
        em.method_name = "execute_command"
        em.obj = object()
        em.args = (1, 2, 3)
        em.kwargs = {"key": "value"}
        em.return_value = "OK"

        assert em.method_name == "execute_command"
        assert em.args == (1, 2, 3)
        assert em.kwargs == {"key": "value"}
        assert em.return_value == "OK"
