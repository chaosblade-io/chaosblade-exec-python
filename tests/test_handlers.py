"""Tests for CreateHandler, DestroyHandler, StatusHandler, and ListHandler."""

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult
from chaosblade.common.transport.request import Request
from chaosblade.common.transport.response import Code
from chaosblade.service.handler.create_handler import CreateHandler
from chaosblade.service.handler.destroy_handler import DestroyHandler
from chaosblade.service.handler.list_handler import ListHandler
from chaosblade.service.handler.status_handler import StatusHandler


# --- Test helpers ---

class FakeExecutor:
    def __init__(self):
        self.called = False

    def run(self, enhancer_model):
        self.called = True


class FakeActionSpec:
    def __init__(self, name, executor=None):
        self._name = name
        self._executor = executor or FakeExecutor()

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


def _register_model_spec(target="redis", action="delay"):
    spec = FakeModelSpec(target)
    spec.add_action_spec(FakeActionSpec(action))
    ManagerFactory.get_model_spec_manager().register_model_spec(spec)
    return spec


# --- CreateHandler tests ---

class TestCreateHandler:
    def test_missing_suid(self):
        handler = CreateHandler()
        resp = handler.handle(Request({"target": "redis", "action": "delay"}))
        assert resp.code == Code.ILLEGAL_PARAMETER
        assert "suid" in resp.error

    def test_missing_target(self):
        handler = CreateHandler()
        resp = handler.handle(Request({"suid": "uid1", "action": "delay"}))
        assert resp.code == Code.ILLEGAL_PARAMETER
        assert "target" in resp.error

    def test_missing_action(self):
        handler = CreateHandler()
        resp = handler.handle(Request({"suid": "uid1", "target": "redis"}))
        assert resp.code == Code.ILLEGAL_PARAMETER
        assert "action" in resp.error

    def test_target_not_found(self):
        handler = CreateHandler()
        resp = handler.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))
        assert resp.code == Code.NOT_FOUND
        assert "not supported" in resp.error

    def test_action_not_found(self):
        _register_model_spec("redis", "delay")
        handler = CreateHandler()
        resp = handler.handle(Request({"suid": "uid1", "target": "redis", "action": "bogus"}))
        assert resp.code == Code.NOT_FOUND

    def test_success(self):
        _register_model_spec("redis", "delay")
        handler = CreateHandler()
        resp = handler.handle(Request({
            "suid": "uid1", "target": "redis", "action": "delay", "time": "3000"
        }))
        assert resp.success is True
        assert resp.code == Code.OK
        # Experiment should be registered
        assert ManagerFactory.get_status_manager().exp_exists("redis")

    def test_duplicate(self):
        _register_model_spec("redis", "delay")
        handler = CreateHandler()
        handler.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))
        resp = handler.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))
        assert resp.code == Code.DUPLICATE_INJECTION

    def test_unloaded_state(self):
        handler = CreateHandler()
        handler.unload()
        resp = handler.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))
        assert resp.code == Code.ILLEGAL_STATE


# --- DestroyHandler tests ---

class TestDestroyHandler:
    def test_destroy_by_uid(self):
        _register_model_spec("redis", "delay")
        create = CreateHandler()
        create.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))

        handler = DestroyHandler()
        resp = handler.handle(Request({"suid": "uid1"}))
        assert resp.success is True
        assert not ManagerFactory.get_status_manager().exp_exists("redis")

    def test_destroy_by_uid_not_found(self):
        handler = DestroyHandler()
        resp = handler.handle(Request({"suid": "nonexist"}))
        assert resp.code == Code.NOT_FOUND

    def test_destroy_by_target_action(self):
        _register_model_spec("redis", "delay")
        create = CreateHandler()
        create.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))
        create.handle(Request({"suid": "uid2", "target": "redis", "action": "delay"}))

        handler = DestroyHandler()
        resp = handler.handle(Request({"target": "redis", "action": "delay"}))
        assert resp.success is True
        assert not ManagerFactory.get_status_manager().exp_exists("redis")

    def test_destroy_missing_params(self):
        handler = DestroyHandler()
        resp = handler.handle(Request({}))
        assert resp.code == Code.ILLEGAL_PARAMETER

    def test_unloaded_state(self):
        handler = DestroyHandler()
        handler.unload()
        resp = handler.handle(Request({"suid": "uid1"}))
        assert resp.code == Code.ILLEGAL_STATE


# --- StatusHandler tests ---

class TestStatusHandler:
    def test_status_found(self):
        _register_model_spec("redis", "delay")
        create = CreateHandler()
        create.handle(Request({"suid": "uid1", "target": "redis", "action": "delay"}))

        handler = StatusHandler()
        resp = handler.handle(Request({"suid": "uid1"}))
        assert resp.success is True
        assert '"count"' in resp.result

    def test_status_not_found(self):
        handler = StatusHandler()
        resp = handler.handle(Request({"suid": "nonexist"}))
        assert resp.code == Code.NOT_FOUND

    def test_status_missing_suid(self):
        handler = StatusHandler()
        resp = handler.handle(Request({}))
        assert resp.code == Code.ILLEGAL_PARAMETER


# --- ListHandler tests ---

class TestListHandler:
    def test_list_empty(self):
        handler = ListHandler()
        request = Request({})
        resp = handler.handle(request)
        assert resp.success is True
        assert resp.result == []

    def test_list_with_experiments(self):
        handler = ListHandler()
        status_manager = ManagerFactory.get_status_manager()

        model1 = Model("redis", "delay")
        model1.matcher.add("cmd", "GET")
        status_manager.register_exp("uid-001", model1)

        model2 = Model("mysql", "exception")
        model2.matcher.add("sql-regex", "SELECT.*")
        status_manager.register_exp("uid-002", model2)

        request = Request({})
        resp = handler.handle(request)
        assert resp.success is True
        assert len(resp.result) == 2

        uids = {exp["uid"] for exp in resp.result}
        assert "uid-001" in uids
        assert "uid-002" in uids

    def test_list_filter_by_target(self):
        handler = ListHandler()
        status_manager = ManagerFactory.get_status_manager()

        status_manager.register_exp("uid-r1", Model("redis", "delay"))
        status_manager.register_exp("uid-m1", Model("mysql", "delay"))

        request = Request({"target": "redis"})
        resp = handler.handle(request)
        assert resp.success is True
        assert len(resp.result) == 1
        assert resp.result[0]["target"] == "redis"

    def test_list_filter_by_target_and_action(self):
        handler = ListHandler()
        status_manager = ManagerFactory.get_status_manager()

        status_manager.register_exp("uid-1", Model("redis", "delay"))
        status_manager.register_exp("uid-2", Model("redis", "exception"))

        request = Request({"target": "redis", "action": "delay"})
        resp = handler.handle(request)
        assert resp.success is True
        assert len(resp.result) == 1
        assert resp.result[0]["action"] == "delay"
