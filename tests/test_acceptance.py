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

"""验收测试 — 站在用户使用角度的端到端功能验证。

测试分类：
  CAT-01: Agent 生命周期管理
  CAT-02: HTTP API 接口（GET/POST/CORS）
  CAT-03: 实验全生命周期（创建/查询/列表/销毁）
  CAT-04: 故障注入能力 — 延迟
  CAT-05: 故障注入能力 — 异常
  CAT-06: 故障注入能力 — 返回值篡改
  CAT-07: 匹配器系统（精确匹配/正则/大小写/effect-count/effect-percent）
  CAT-08: 插件系统（Redis/HTTP/MySQL/gRPC/Kafka/SQLAlchemy）
  CAT-09: ImportHook 延迟加载
  CAT-10: MonkeyPatcher 引擎
  CAT-11: CLI 命令（attach/detach/status）
  CAT-12: 配置管理（环境变量/文件/优先级）
  CAT-13: 异常与边界场景
  CAT-14: 并发安全
  CAT-15: 直接注入执行器（CPU/Memory）
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import tempfile
import threading
import time
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.request import urlopen, Request as HttpRequest

import pytest

from chaosblade.bootstrap.agent import ChaosBladeAgent
from chaosblade.bootstrap.enhancer_factory import EnhancerFactory
from chaosblade.bootstrap.import_hook import ImportHook
from chaosblade.bootstrap.patcher import MonkeyPatcher
from chaosblade.cli import cmd_attach, cmd_detach, SITECUSTOMIZE_MARKER
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
from chaosblade.common.transport.request import Request as CbRequest
from chaosblade.common.transport.response import Code, Response
from chaosblade.config import AgentConfig
from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor
from chaosblade.plugins.base import DefaultActionSpec, DefaultFlagSpec, DefaultPointCut
from chaosblade.plugins.default_enhancer import DefaultBeforeEnhancer
from chaosblade.service.handler.create_handler import CreateHandler
from chaosblade.service.handler.destroy_handler import DestroyHandler
from chaosblade.service.handler.health_handler import HealthHandler
from chaosblade.service.handler.list_handler import ListHandler
from chaosblade.service.handler.status_handler import StatusHandler
from chaosblade.service.server import start_server


# ===========================================================================
# Test Helpers
# ===========================================================================

class FakeExecutor:
    def __init__(self, raise_interrupt=False, return_value=None):
        self.called = False
        self.call_count = 0
        self._raise_interrupt = raise_interrupt
        self._return_value = return_value

    def run(self, enhancer_model):
        self.called = True
        self.call_count += 1
        if self._raise_interrupt:
            throw_return_immediately(self._return_value or "injected")


class FakeActionSpec:
    def __init__(self, name, executor=None, aliases=None, required_flags=None):
        self._name = name
        self._executor = executor or FakeExecutor()
        self._aliases = aliases or []
        self._required_flags = required_flags or []

    def get_name(self): return self._name
    def get_aliases(self): return self._aliases
    def get_short_desc(self): return ""
    def get_long_desc(self): return ""
    def get_action_flags(self): return self._required_flags

    def predicate(self, action_model):
        return PredicateResult.ok()

    def get_action_executor(self):
        return self._executor


class FakeModelSpec(BaseModelSpec):
    def __init__(self, target="redis"):
        super().__init__()
        self._target = target

    def get_target(self): return self._target
    def get_short_desc(self): return f"{self._target} test"
    def get_long_desc(self): return ""
    def get_matcher_specs(self): return []


def _register_model(target="redis", action="delay", executor=None):
    spec = FakeModelSpec(target)
    spec.add_action_spec(FakeActionSpec(action, executor=executor))
    ManagerFactory.get_model_spec_manager().register_model_spec(spec)
    return spec


def _http_get(url):
    with urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode())


def _http_post(url, body=None):
    data = json.dumps(body or {}).encode()
    req = HttpRequest(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(data)))
    with urlopen(req, data, timeout=5) as resp:
        return json.loads(resp.read().decode()), resp.headers


# ===========================================================================
# CAT-01: Agent 生命周期管理
# ===========================================================================

class TestCAT01_AgentLifecycle:
    """验证 Agent 的启动、停止和重入安全。"""

    def test_01_agent_start_and_stop(self):
        """AC-0101: Agent 能够正常启动并监听指定端口。"""
        agent = ChaosBladeAgent(port=0, host="127.0.0.1")
        agent.start()
        assert agent._started is True
        agent.stop()
        assert agent._started is False

    def test_02_agent_double_start_safe(self):
        """AC-0102: 重复调用 start() 不会抛出异常。"""
        agent = ChaosBladeAgent(port=0, host="127.0.0.1")
        agent.start()
        agent.start()  # 第二次应安全
        assert agent._started is True
        agent.stop()

    def test_03_agent_double_stop_safe(self):
        """AC-0103: 重复调用 stop() 不会抛出异常。"""
        agent = ChaosBladeAgent(port=0, host="127.0.0.1")
        agent.start()
        agent.stop()
        agent.stop()  # 第二次应安全

    def test_04_sigterm_handler_registered(self):
        """AC-0104: Agent 启动后注册 SIGTERM 信号处理器。"""
        old_handler = signal.getsignal(signal.SIGTERM)
        agent = ChaosBladeAgent(port=0, host="127.0.0.1")
        agent.start()
        new_handler = signal.getsignal(signal.SIGTERM)
        assert new_handler != old_handler
        agent.stop()
        signal.signal(signal.SIGTERM, old_handler)

    def test_05_agent_cleanup_patches_on_stop(self):
        """AC-0105: Agent 停止时清理所有 MonkeyPatch。"""
        agent = ChaosBladeAgent(port=0, host="127.0.0.1")
        agent.start()

        # 模拟一个 patch
        mod = types.ModuleType("_test_accept_cleanup")
        mod.func = lambda: "original"
        sys.modules["_test_accept_cleanup"] = mod
        agent.patcher.apply_patch("cleanup-test", "_test_accept_cleanup", "func",
                                  lambda orig, *a, **kw: "patched")
        assert mod.func() == "patched"

        agent.stop()
        assert mod.func() == "original"
        del sys.modules["_test_accept_cleanup"]


# ===========================================================================
# CAT-02: HTTP API 接口
# ===========================================================================

class TestCAT02_HTTPAPI:
    """验证 HTTP Server 的 GET/POST/CORS 支持。"""

    def setup_method(self):
        ManagerFactory.load()
        self.server = start_server(0, "127.0.0.1")
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def teardown_method(self):
        self.server.shutdown()
        ManagerFactory.unload()

    def test_01_get_health(self):
        """AC-0201: GET /health 返回正常响应。"""
        data = _http_get(f"{self.base}/health")
        assert data["success"] is True
        assert data["result"]["status"] == "running"

    def test_02_post_health(self):
        """AC-0202: POST /health 同样有效。"""
        data, _ = _http_post(f"{self.base}/health")
        assert data["success"] is True

    def test_03_cors_headers_on_get(self):
        """AC-0203: GET 响应包含 CORS 头。"""
        with urlopen(f"{self.base}/health", timeout=5) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"

    def test_04_options_preflight(self):
        """AC-0204: OPTIONS 预检请求返回 204 + CORS 头。"""
        req = HttpRequest(f"{self.base}/health", method="OPTIONS")
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 204
            assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

    def test_05_unknown_command_404(self):
        """AC-0205: 未知命令返回 404。"""
        data = _http_get(f"{self.base}/nonexist")
        assert data["code"] == 404

    def test_06_post_with_json_body(self):
        """AC-0206: POST 请求正确解析 JSON Body 参数。"""
        _register_model("redis", "delay")
        body = {"suid": "http-test", "target": "redis", "action": "delay", "time": "100"}
        data, _ = _http_post(f"{self.base}/create", body)
        assert data["success"] is True


# ===========================================================================
# CAT-03: 实验全生命周期
# ===========================================================================

class TestCAT03_ExperimentLifecycle:
    """验证实验的创建、查询、列表、销毁全流程。"""

    def setup_method(self):
        ManagerFactory.load()
        self.server = start_server(0, "127.0.0.1")
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        _register_model("redis", "delay")

    def teardown_method(self):
        self.server.shutdown()
        ManagerFactory.unload()

    def test_01_create_experiment(self):
        """AC-0301: 创建实验成功返回 200。"""
        data = _http_get(f"{self.base}/create?suid=exp1&target=redis&action=delay&time=3000")
        assert data["success"] is True
        assert data["code"] == 200

    def test_02_status_experiment(self):
        """AC-0302: 查询实验状态返回命中计数。"""
        _http_get(f"{self.base}/create?suid=exp2&target=redis&action=delay")
        data = _http_get(f"{self.base}/status?suid=exp2")
        assert data["success"] is True
        result = json.loads(data["result"])
        assert "count" in result

    def test_03_list_experiments(self):
        """AC-0303: 列表返回所有活跃实验。"""
        _http_get(f"{self.base}/create?suid=exp3a&target=redis&action=delay")
        _http_get(f"{self.base}/create?suid=exp3b&target=redis&action=delay")
        data = _http_get(f"{self.base}/list")
        assert data["success"] is True
        assert len(data["result"]) == 2

    def test_04_destroy_by_uid(self):
        """AC-0304: 按 UID 销毁实验。"""
        _http_get(f"{self.base}/create?suid=exp4&target=redis&action=delay")
        data = _http_get(f"{self.base}/destroy?suid=exp4")
        assert data["success"] is True
        # 验证已销毁
        data = _http_get(f"{self.base}/status?suid=exp4")
        assert data["code"] == 404

    def test_05_destroy_by_target_action(self):
        """AC-0305: 按 target+action 批量销毁实验。"""
        _http_get(f"{self.base}/create?suid=exp5a&target=redis&action=delay")
        _http_get(f"{self.base}/create?suid=exp5b&target=redis&action=delay")
        data = _http_get(f"{self.base}/destroy?target=redis&action=delay")
        assert data["success"] is True
        data = _http_get(f"{self.base}/list")
        assert data["result"] == []

    def test_06_list_filter_by_target(self):
        """AC-0306: 列表支持按 target 过滤。"""
        _register_model("mysql", "delay")
        _http_get(f"{self.base}/create?suid=exp6a&target=redis&action=delay")
        _http_get(f"{self.base}/create?suid=exp6b&target=mysql&action=delay")
        data = _http_get(f"{self.base}/list?target=redis")
        assert len(data["result"]) == 1
        assert data["result"][0]["target"] == "redis"


# ===========================================================================
# CAT-04: 故障注入 — 延迟
# ===========================================================================

class TestCAT04_DelayInjection:
    """验证延迟注入执行器的正确性。"""

    def test_01_delay_basic(self):
        """AC-0401: 延迟注入按指定时间生效。"""
        executor = DelayActionExecutor()
        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.merge(Model("test", "delay"))
        em.action_model.add_flag("time", "50")

        start = time.time()
        executor.run(em)
        elapsed = (time.time() - start) * 1000
        assert elapsed >= 45  # 允许少量误差

    def test_02_delay_with_offset(self):
        """AC-0402: 延迟注入支持随机偏移。"""
        executor = DelayActionExecutor()
        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.merge(Model("test", "delay"))
        em.action_model.add_flag("time", "50")
        em.action_model.add_flag("offset", "20")

        start = time.time()
        executor.run(em)
        elapsed = (time.time() - start) * 1000
        # 应在 30~70ms 之间
        assert 25 <= elapsed <= 80


# ===========================================================================
# CAT-05: 故障注入 — 异常
# ===========================================================================

class TestCAT05_ExceptionInjection:
    """验证异常注入执行器的正确性。"""

    def test_01_throw_runtime_error(self):
        """AC-0501: 注入 RuntimeError 异常。"""
        executor = ThrowExceptionExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "exception"))
        em.action_model.add_flag("exception", "RuntimeError")
        em.action_model.add_flag("exception-message", "injected fault")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.state == ProcessState.THROWS_IMMEDIATELY
        assert isinstance(exc_info.value.exception, RuntimeError)
        assert "injected fault" in str(exc_info.value.exception)

    def test_02_throw_connection_error(self):
        """AC-0502: 注入 ConnectionError 异常。"""
        executor = ThrowExceptionExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "exception"))
        em.action_model.add_flag("exception", "ConnectionError")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert isinstance(exc_info.value.exception, ConnectionError)

    def test_03_throw_default_when_no_flag(self):
        """AC-0503: 未指定异常类型时默认抛出 RuntimeError。"""
        executor = ThrowExceptionExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "exception"))

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert isinstance(exc_info.value.exception, RuntimeError)


# ===========================================================================
# CAT-06: 故障注入 — 返回值篡改
# ===========================================================================

class TestCAT06_ReturnValueInjection:
    """验证返回值篡改执行器的正确性。"""

    def test_01_return_string(self):
        """AC-0601: 篡改返回值为字符串。"""
        executor = ReturnValueExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "return"))
        em.action_model.add_flag("return-value", "hello_world")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.response == "hello_world"

    def test_02_return_null(self):
        """AC-0602: 篡改返回值为 None。"""
        executor = ReturnValueExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "return"))
        em.action_model.add_flag("return-value", "null")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.response is None

    def test_03_return_json_object(self):
        """AC-0603: 篡改返回值为 JSON 对象。"""
        executor = ReturnValueExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "return"))
        em.action_model.add_flag("return-value", '{"status": "error"}')

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.response == {"status": "error"}

    def test_04_return_integer(self):
        """AC-0604: 篡改返回值为整数。"""
        executor = ReturnValueExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "return"))
        em.action_model.add_flag("return-value", "42")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.response == 42

    def test_05_return_boolean(self):
        """AC-0605: 篡改返回值为布尔值。"""
        executor = ReturnValueExecutor()
        em = EnhancerModel()
        em.merge(Model("test", "return"))
        em.action_model.add_flag("return-value", "false")

        with pytest.raises(InterruptProcessException) as exc_info:
            executor.run(em)
        assert exc_info.value.response is False


# ===========================================================================
# CAT-07: 匹配器系统
# ===========================================================================

class TestCAT07_MatcherSystem:
    """验证 Injector 的匹配逻辑。"""

    def _setup_exp(self, matchers=None, executor=None):
        if executor is None:
            executor = FakeExecutor()
        spec = FakeModelSpec("redis")
        spec.add_action_spec(FakeActionSpec("delay", executor=executor))
        ManagerFactory.get_model_spec_manager().register_model_spec(spec)
        model = Model("redis", "delay")
        if matchers:
            for k, v in matchers.items():
                model.matcher.add(k, v)
        ManagerFactory.get_status_manager().register_exp("uid-match", model)
        return executor

    def test_01_exact_match(self):
        """AC-0701: 精确匹配生效。"""
        executor = self._setup_exp({"cmd": "GET"})
        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is True

    def test_02_exact_match_miss(self):
        """AC-0702: 精确匹配不命中时不触发。"""
        executor = self._setup_exp({"cmd": "GET"})
        mm = MatcherModel()
        mm.add("cmd", "SET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is False

    def test_03_case_insensitive_match(self):
        """AC-0703: 匹配不区分大小写。"""
        executor = self._setup_exp({"cmd": "get"})
        mm = MatcherModel()
        mm.add("cmd", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is True

    def test_04_regex_match(self):
        """AC-0704: 正则匹配生效（-regex 后缀）。"""
        executor = self._setup_exp({"cmd-regex": "GET|MGET"})
        mm = MatcherModel()
        mm.add("cmd-regex", "GET")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is True

    def test_05_effect_count_limit(self):
        """AC-0705: effect-count 限制命中次数。"""
        executor = self._setup_exp({"effect-count": "3"})
        for i in range(5):
            mm = MatcherModel()
            em = EnhancerModel(matcher_model=mm)
            em.target = "redis"
            try:
                Injector.inject(em)
            except InterruptProcessException:
                pass
        metric = ManagerFactory.get_status_manager().get_status_metric_by_uid("uid-match")
        assert metric.count == 3

    def test_06_effect_percent_zero(self):
        """AC-0706: effect-percent=0 完全不注入。"""
        executor = self._setup_exp({"effect-percent": "0"})
        mm = MatcherModel()
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is False

    def test_07_empty_matchers_match_all(self):
        """AC-0707: 无匹配器时匹配所有请求。"""
        executor = self._setup_exp({})
        mm = MatcherModel()
        mm.add("cmd", "WHATEVER")
        em = EnhancerModel(matcher_model=mm)
        em.target = "redis"
        Injector.inject(em)
        assert executor.called is True


# ===========================================================================
# CAT-08: 插件系统
# ===========================================================================

class TestCAT08_PluginSystem:
    """验证所有官方插件的接口正确性。"""

    def test_01_redis_plugin(self):
        """AC-0801: Redis 插件接口完整。"""
        from chaosblade.plugins.redis import RedisPlugin, _redis_matcher_extractor
        p = RedisPlugin()
        assert p.get_name() == "redis"
        assert p.get_point_cut().get_target_module() == "redis.client"
        assert p.get_model_spec().get_action_spec("delay") is not None
        # 测试 matcher extractor
        matchers = _redis_matcher_extractor("execute_command", None, (None, "GET", "user:1"), {})
        assert matchers["cmd"] == "GET"
        assert matchers["key"] == "user:1"

    def test_02_requests_plugin(self):
        """AC-0802: HTTP/Requests 插件接口完整。"""
        from chaosblade.plugins.requests import RequestsPlugin, _requests_matcher_extractor
        p = RequestsPlugin()
        assert p.get_name() == "http"
        assert p.get_point_cut().get_target_class() == "HTTPAdapter"
        # 测试 matcher extractor
        class FakeReq:
            url = "http://example.com/api"
            method = "POST"
        matchers = _requests_matcher_extractor("send", None, (None, FakeReq()), {})
        assert matchers["url"] == "http://example.com/api"
        assert matchers["method"] == "POST"
        assert matchers["host"] == "example.com"

    def test_03_mysql_plugin(self):
        """AC-0803: MySQL 插件接口完整。"""
        from chaosblade.plugins.mysql import MysqlPlugin, PyMysqlPlugin, _mysql_matcher_extractor
        p1 = MysqlPlugin()
        p2 = PyMysqlPlugin()
        assert p1.get_name() == "mysql"
        assert p2.get_name() == "pymysql"
        assert p1.get_point_cut().get_target_class() == "MySQLCursor"
        assert p2.get_point_cut().get_target_class() == "Cursor"
        # 测试 matcher extractor
        matchers = _mysql_matcher_extractor("execute", None, (None, "SELECT * FROM users"), {})
        assert matchers["sql"] == "SELECT * FROM users"
        assert matchers["sqltype"] == "SELECT"

    def test_04_grpc_plugin(self):
        """AC-0804: gRPC 插件接口完整。"""
        from chaosblade.plugins.grpc import GrpcPlugin, _grpc_matcher_extractor
        p = GrpcPlugin()
        assert p.get_name() == "grpc"
        assert p.get_point_cut().get_target_function() == "__call__"
        # 测试 matcher extractor
        class FakeStub:
            _method = b"/pkg.UserService/GetUser"
        matchers = _grpc_matcher_extractor("__call__", FakeStub(), (), {})
        assert matchers["method"] == "/pkg.UserService/GetUser"
        assert matchers["service"] == "pkg.UserService"

    def test_05_kafka_plugin(self):
        """AC-0805: Kafka 插件接口完整（producer + consumer）。"""
        from chaosblade.plugins.kafka import (
            KafkaProducerPlugin, KafkaConsumerPlugin,
            _kafka_producer_matcher_extractor, _kafka_consumer_matcher_extractor,
        )
        p1 = KafkaProducerPlugin()
        p2 = KafkaConsumerPlugin()
        assert p1.get_name() == "kafka-producer"
        assert p2.get_name() == "kafka-consumer"
        # Producer matcher
        matchers = _kafka_producer_matcher_extractor("send", None, (None, "orders"), {})
        assert matchers["topic"] == "orders"
        assert matchers["operation"] == "produce"

    def test_06_sqlalchemy_plugin(self):
        """AC-0806: SQLAlchemy 插件接口完整。"""
        from chaosblade.plugins.sqlalchemy import SqlalchemyPlugin, _sqlalchemy_matcher_extractor
        p = SqlalchemyPlugin()
        assert p.get_name() == "sqlalchemy"
        assert p.get_point_cut().get_target_class() == "Connection"
        matchers = _sqlalchemy_matcher_extractor("execute", None, (None, "INSERT INTO t VALUES (1)"), {})
        assert matchers["sql"] == "INSERT INTO t VALUES (1)"
        assert matchers["sqltype"] == "INSERT"

    def test_07_all_plugins_have_three_actions(self):
        """AC-0807: 所有插件均支持 delay/exception/return 三种 action。"""
        from chaosblade.plugins.redis import RedisModelSpec
        from chaosblade.plugins.requests import RequestsModelSpec
        from chaosblade.plugins.mysql import MysqlModelSpec
        from chaosblade.plugins.grpc import GrpcModelSpec
        from chaosblade.plugins.kafka import KafkaModelSpec
        from chaosblade.plugins.sqlalchemy import SqlalchemyModelSpec

        for SpecClass in [RedisModelSpec, RequestsModelSpec, MysqlModelSpec,
                          GrpcModelSpec, KafkaModelSpec, SqlalchemyModelSpec]:
            spec = SpecClass()
            assert spec.get_action_spec("delay") is not None, f"{SpecClass.__name__} missing delay"
            assert spec.get_action_spec("throwCustomException") is not None
            assert spec.get_action_spec("returnValue") is not None


# ===========================================================================
# CAT-09: ImportHook 延迟加载
# ===========================================================================

class TestCAT09_ImportHook:
    """验证 ImportHook 延迟补丁机制。"""

    def setup_method(self):
        self.patcher = MonkeyPatcher()
        self.hook = ImportHook(self.patcher)
        for k in list(sys.modules.keys()):
            if k.startswith("_accept_hook_"):
                del sys.modules[k]

    def teardown_method(self):
        self.hook.uninstall()
        self.patcher.remove_all()
        for k in list(sys.modules.keys()):
            if k.startswith("_accept_hook_"):
                del sys.modules[k]

    def test_01_immediate_patch(self):
        """AC-0901: 模块已加载时立即应用 patch。"""
        mod = types.ModuleType("_accept_hook_loaded")
        mod.fn = lambda: "original"
        sys.modules["_accept_hook_loaded"] = mod

        self.hook.register_pending("im-01", "_accept_hook_loaded", "fn",
                                   lambda orig, *a, **kw: "patched")
        assert mod.fn() == "patched"
        assert self.hook.pending_count == 0

    def test_02_deferred_patch(self):
        """AC-0902: 模块未加载时注册 pending，加载后自动应用。"""
        self.hook.register_pending("df-01", "_accept_hook_deferred", "fn",
                                   lambda orig, *a, **kw: "deferred_patched")
        assert self.hook.pending_count == 1

        mod = types.ModuleType("_accept_hook_deferred")
        mod.fn = lambda: "original"
        sys.modules["_accept_hook_deferred"] = mod
        self.hook._apply_pending("_accept_hook_deferred")

        assert mod.fn() == "deferred_patched"
        assert self.hook.pending_count == 0

    def test_03_install_uninstall(self):
        """AC-0903: install/uninstall 正确修改 sys.meta_path。"""
        self.hook.install()
        assert self.hook in sys.meta_path
        self.hook.uninstall()
        assert self.hook not in sys.meta_path


# ===========================================================================
# CAT-10: MonkeyPatcher 引擎
# ===========================================================================

class TestCAT10_MonkeyPatcher:
    """验证 MonkeyPatcher 的核心补丁能力。"""

    def setup_method(self):
        self.patcher = MonkeyPatcher()
        for k in list(sys.modules.keys()):
            if k.startswith("_accept_patch_"):
                del sys.modules[k]

    def teardown_method(self):
        self.patcher.remove_all()
        for k in list(sys.modules.keys()):
            if k.startswith("_accept_patch_"):
                del sys.modules[k]

    def test_01_patch_module_function(self):
        """AC-1001: 补丁模块级函数。"""
        mod = types.ModuleType("_accept_patch_01")
        mod.add = lambda a, b: a + b
        sys.modules["_accept_patch_01"] = mod

        self.patcher.apply_patch("p01", "_accept_patch_01", "add",
                                 lambda orig, *a, **kw: orig(*a, **kw) * 10)
        assert mod.add(2, 3) == 50

    def test_02_patch_class_method(self):
        """AC-1002: 补丁类实例方法。"""
        mod = types.ModuleType("_accept_patch_02")
        class Svc:
            def call(self, x): return x
        mod.Svc = Svc
        sys.modules["_accept_patch_02"] = mod

        self.patcher.apply_patch("p02", "_accept_patch_02", "call",
                                 lambda orig, *a, **kw: "intercepted",
                                 target_class="Svc")
        assert Svc().call(123) == "intercepted"

    def test_03_remove_restores_original(self):
        """AC-1003: 移除补丁恢复原始行为。"""
        mod = types.ModuleType("_accept_patch_03")
        mod.fn = lambda: "original"
        sys.modules["_accept_patch_03"] = mod

        self.patcher.apply_patch("p03", "_accept_patch_03", "fn",
                                 lambda orig, *a, **kw: "patched")
        assert mod.fn() == "patched"
        self.patcher.remove_patch("p03")
        assert mod.fn() == "original"

    def test_04_remove_all(self):
        """AC-1004: remove_all 清除所有补丁。"""
        mod = types.ModuleType("_accept_patch_04")
        mod.f1 = lambda: "a"
        mod.f2 = lambda: "b"
        sys.modules["_accept_patch_04"] = mod

        self.patcher.apply_patch("pa", "_accept_patch_04", "f1", lambda o, *a, **k: "x")
        self.patcher.apply_patch("pb", "_accept_patch_04", "f2", lambda o, *a, **k: "y")
        assert self.patcher.get_patch_count() == 2

        count = self.patcher.remove_all()
        assert count == 2
        assert mod.f1() == "a"
        assert mod.f2() == "b"

    def test_05_async_patch(self):
        """AC-1005: 支持异步函数补丁。"""
        mod = types.ModuleType("_accept_patch_05")
        async def async_fn(): return "async_original"
        mod.async_fn = async_fn
        sys.modules["_accept_patch_05"] = mod

        self.patcher.apply_patch("p05", "_accept_patch_05", "async_fn",
                                 lambda orig, *a, **kw: "async_patched")
        import inspect
        assert inspect.iscoroutinefunction(mod.async_fn)


# ===========================================================================
# CAT-11: CLI 命令
# ===========================================================================

class TestCAT11_CLI:
    """验证 CLI 的 attach/detach 功能。"""

    def test_01_attach_creates_sitecustomize(self):
        """AC-1101: attach 创建 sitecustomize.py。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = type("A", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})()
            assert cmd_attach(args) == 0
            path = Path(tmpdir) / "sitecustomize.py"
            assert path.exists()
            content = path.read_text()
            assert SITECUSTOMIZE_MARKER in content
            assert "ChaosBladeAgent" in content

    def test_02_attach_idempotent(self):
        """AC-1102: 重复 attach 不会重复注入。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = type("A", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})()
            cmd_attach(args)
            cmd_attach(args)
            content = (Path(tmpdir) / "sitecustomize.py").read_text()
            assert content.count(SITECUSTOMIZE_MARKER) == 1

    def test_03_detach_removes_file(self):
        """AC-1103: detach 移除 sitecustomize.py。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd_attach(type("A", (), {"target_dir": tmpdir, "host": "127.0.0.1", "port": 9526})())
            assert cmd_detach(type("A", (), {"target_dir": tmpdir})()) == 0
            assert not (Path(tmpdir) / "sitecustomize.py").exists()

    def test_04_detach_no_file_returns_1(self):
        """AC-1104: detach 无文件时返回 1。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert cmd_detach(type("A", (), {"target_dir": tmpdir})()) == 1


# ===========================================================================
# CAT-12: 配置管理
# ===========================================================================

class TestCAT12_Configuration:
    """验证配置加载优先级。"""

    def test_01_default_config(self):
        """AC-1201: 默认配置值正确。"""
        config = AgentConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 9526
        assert config.debug is False

    def test_02_env_override(self):
        """AC-1202: 环境变量覆盖默认值。"""
        with patch.dict(os.environ, {"CHAOSBLADE_PORT": "8888"}):
            config = AgentConfig.load()
            assert config.port == 8888

    def test_03_json_file_config(self):
        """AC-1203: JSON 文件加载配置。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"host": "10.0.0.1", "port": 5555}')
            f.flush()
            config = AgentConfig.load(config_path=f.name)
            assert config.host == "10.0.0.1"
            assert config.port == 5555
        os.unlink(f.name)

    def test_04_env_overrides_file(self):
        """AC-1204: 环境变量优先于配置文件。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"port": 1111}')
            f.flush()
            with patch.dict(os.environ, {"CHAOSBLADE_PORT": "2222"}):
                config = AgentConfig.load(config_path=f.name)
                assert config.port == 2222
        os.unlink(f.name)


# ===========================================================================
# CAT-13: 异常与边界场景
# ===========================================================================

class TestCAT13_ErrorHandling:
    """验证各种错误场景的处理。"""

    def test_01_create_missing_suid(self):
        """AC-1301: 缺少 suid 返回参数错误。"""
        handler = CreateHandler()
        resp = handler.handle(CbRequest({"target": "redis", "action": "delay"}))
        assert resp.code == Code.ILLEGAL_PARAMETER

    def test_02_create_unknown_target(self):
        """AC-1302: 未知 target 返回 NOT_FOUND。"""
        handler = CreateHandler()
        resp = handler.handle(CbRequest({"suid": "x", "target": "unknown", "action": "delay"}))
        assert resp.code == Code.NOT_FOUND

    def test_03_create_duplicate_uid(self):
        """AC-1303: 重复 UID 返回 DUPLICATE_INJECTION。"""
        _register_model("redis", "delay")
        handler = CreateHandler()
        handler.handle(CbRequest({"suid": "dup1", "target": "redis", "action": "delay"}))
        resp = handler.handle(CbRequest({"suid": "dup1", "target": "redis", "action": "delay"}))
        assert resp.code == Code.DUPLICATE_INJECTION

    def test_04_destroy_nonexist_uid(self):
        """AC-1304: 销毁不存在的 UID 返回 NOT_FOUND。"""
        handler = DestroyHandler()
        resp = handler.handle(CbRequest({"suid": "nonexist"}))
        assert resp.code == Code.NOT_FOUND

    def test_05_status_missing_suid(self):
        """AC-1305: 状态查询缺少 suid 返回参数错误。"""
        handler = StatusHandler()
        resp = handler.handle(CbRequest({}))
        assert resp.code == Code.ILLEGAL_PARAMETER

    def test_06_handler_unloaded_state(self):
        """AC-1306: 卸载后的 handler 拒绝请求。"""
        handler = CreateHandler()
        handler.unload()
        resp = handler.handle(CbRequest({"suid": "x", "target": "y", "action": "z"}))
        assert resp.code == Code.ILLEGAL_STATE

    def test_07_response_non_serializable(self):
        """AC-1307: Response 能处理不可序列化对象。"""
        resp = Response.of_success({"obj": object()})
        result = resp.to_json()  # 不应抛出异常
        assert "result" in result


# ===========================================================================
# CAT-14: 并发安全
# ===========================================================================

class TestCAT14_Concurrency:
    """验证并发场景下的线程安全。"""

    def test_01_concurrent_experiment_registration(self):
        """AC-1401: 并发注册实验不丢数据。"""
        status_manager = ManagerFactory.get_status_manager()
        errors = []

        def register(i):
            try:
                model = Model("redis", "delay")
                status_manager.register_exp(f"concurrent-{i}", model)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(status_manager.list_uids("redis", "delay")) == 50

    def test_02_concurrent_injector_calls(self):
        """AC-1402: 并发 Injector 调用不崩溃。"""
        executor = FakeExecutor()
        _register_model("redis", "delay", executor=executor)
        model = Model("redis", "delay")
        ManagerFactory.get_status_manager().register_exp("conc-inj", model)

        errors = []

        def inject_call():
            try:
                mm = MatcherModel()
                em = EnhancerModel(matcher_model=mm)
                em.target = "redis"
                Injector.inject(em)
            except InterruptProcessException:
                pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=inject_call) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert executor.called is True


# ===========================================================================
# CAT-15: 直接注入执行器
# ===========================================================================

class TestCAT15_DirectlyExecutors:
    """验证 CPU/Memory 直接注入执行器。"""

    def test_01_cpu_burn_start_stop(self):
        """AC-1501: CPU 燃烧可正常启动和停止。"""
        from chaosblade.executor.directly_executors import CpuBurnExecutor
        executor = CpuBurnExecutor()
        model = Model("jvm", "cpuBurn")
        model.action.add_flag("cpu-count", "1")
        model.action.add_flag("cpu-percent", "50")

        executor.create_injection("cpu-01", model)
        assert executor._running is True
        assert len(executor._workers) == 1

        executor.destroy_injection("cpu-01", model)
        assert executor._running is False

    def test_02_memory_fill_start_stop(self):
        """AC-1502: 内存填充可正常分配和释放。"""
        from chaosblade.executor.directly_executors import MemoryFillExecutor
        executor = MemoryFillExecutor()
        model = Model("jvm", "memFill")
        model.action.add_flag("mem-size", "1")  # 1MB

        executor.create_injection("mem-01", model)
        assert len(executor._allocated) > 0

        executor.destroy_injection("mem-01", model)
        assert len(executor._allocated) == 0
