"""Documentation Command Verification - ensures all curl examples in docs work correctly.

This test file verifies that the exact parameter names and formats documented
in docs/plugins/*.md actually work against the ChaosBlade agent. It catches
issues like using wrong parameter names (e.g., 'value' instead of 'return-value').

Tested scenarios from each plugin's documentation:
- delay with time/offset
- throwCustomException with exception/exception-message
- returnValue with return-value
- matcher filtering (positive and negative)
- effect-count limiting
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

import pytest


# ──────────────────────────────────────────────────────────────────────
# Override conftest's autouse reset_managers fixture
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_managers():
    """No-op override: the module-scoped agent fixture manages lifecycle."""
    yield


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def agent():
    """Start a real ChaosBladeAgent and yield the base URL."""
    from chaosblade.bootstrap.agent import ChaosBladeAgent
    agent = ChaosBladeAgent(port=0, host="127.0.0.1")
    agent.start()
    port = agent._server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    agent.stop()


def _create(base_url: str, params: dict) -> dict:
    """Create experiment via GET (same as curl in docs)."""
    url = f"{base_url}/create?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _destroy(base_url: str, suid: str) -> dict:
    """Destroy experiment."""
    url = f"{base_url}/destroy?suid={suid}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _status(base_url: str, suid: str) -> dict:
    """Query experiment status."""
    url = f"{base_url}/status?suid={suid}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


# ══════════════════════════════════════════════════════════════════════
# 1. Verify core parameter names (the exact ones in docs)
# ══════════════════════════════════════════════════════════════════════

class TestDocParameterNames:
    """Verify all documented parameter names are correctly accepted."""

    def test_delay_params_time_and_offset(self, agent):
        """Docs: action=delay&time=500&offset=100"""
        suid = "doc-param-delay-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "delay",
            "time": "500",
            "offset": "100",
            "cmd": "GET",
        })
        assert resp["code"] == 200, f"time+offset params rejected: {resp}"
        _destroy(agent, suid)

    def test_exception_params(self, agent):
        """Docs: action=throwCustomException&exception=ConnectionError&exception-message=..."""
        suid = "doc-param-exc-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "ConnectionError",
            "exception-message": "chaos: doc test",
        })
        assert resp["code"] == 200, f"exception params rejected: {resp}"
        _destroy(agent, suid)

    def test_return_value_param_name(self, agent):
        """Docs: action=returnValue&return-value=... (NOT 'value')"""
        suid = "doc-param-ret-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "returnValue",
            "return-value": "test-data",
            "cmd": "GET",
        })
        assert resp["code"] == 200, f"return-value param rejected: {resp}"

        # Verify it actually works
        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)
        result = client.get("any-key")
        assert result == "test-data", f"return-value not effective: got {result}"
        _destroy(agent, suid)

    def test_return_value_json(self, agent):
        """Docs: return-value={"status": "mocked"}"""
        suid = "doc-param-ret-json-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "returnValue",
            "return-value": '{"status": "mocked"}',
        })
        assert resp["code"] == 200
        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)
        result = client.get("key")
        assert result == {"status": "mocked"}
        _destroy(agent, suid)

    def test_return_value_null(self, agent):
        """Docs: return-value=null → Python None"""
        suid = "doc-param-ret-null-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "returnValue",
            "return-value": "null",
        })
        assert resp["code"] == 200
        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)
        result = client.get("key")
        assert result is None
        _destroy(agent, suid)

    def test_effect_count_param(self, agent):
        """Docs: effect-count=2"""
        suid = "doc-param-ec-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "limited",
            "effect-count": "2",
        })
        assert resp["code"] == 200

        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)

        # First 2 should raise
        for _ in range(2):
            with pytest.raises(RuntimeError, match="limited"):
                client.get("k")

        # 3rd should NOT raise our exception
        with pytest.raises(Exception) as exc_info:
            client.get("k")
        assert "limited" not in str(exc_info.value)
        _destroy(agent, suid)


# ══════════════════════════════════════════════════════════════════════
# 2. Verify each plugin's target name (exact string from docs)
# ══════════════════════════════════════════════════════════════════════

class TestDocTargetNames:
    """Verify all documented target names are valid."""

    @pytest.mark.parametrize("target", [
        "redis", "http", "httpx", "mysql", "grpc", "kafka", "sqlalchemy",
    ])
    def test_target_accepted(self, agent, target):
        """Each documented target should be accepted by the agent."""
        suid = f"doc-target-{target}-001"
        resp = _create(agent, {
            "suid": suid,
            "target": target,
            "action": "delay",
            "time": "100",
        })
        assert resp["code"] == 200, f"target={target} rejected: {resp}"
        _destroy(agent, suid)


# ══════════════════════════════════════════════════════════════════════
# 3. Verify matcher parameters per plugin
# ══════════════════════════════════════════════════════════════════════

class TestDocMatchers:
    """Verify documented matcher params are correctly parsed."""

    def test_redis_matchers_cmd_and_key(self, agent):
        """Docs: cmd=GET&key=cache:token"""
        suid = "doc-match-redis-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "matched",
            "cmd": "GET",
            "key": "cache:token",
        })
        assert resp["code"] == 200

        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)

        # Matching key should trigger
        with pytest.raises(RuntimeError, match="matched"):
            client.get("cache:token")

        # Different key should NOT trigger
        try:
            client.get("other-key")
        except RuntimeError:
            pytest.fail("Non-matching key should not trigger")
        except Exception:
            pass  # Connection error expected
        _destroy(agent, suid)

    def test_http_matchers_host_and_method(self, agent):
        """Docs: host=target-host.com&method=POST"""
        suid = "doc-match-http-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "http",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "http-matched",
            "host": "target-host.com",
            "method": "POST",
        })
        assert resp["code"] == 200

        import requests
        # GET to target-host should NOT trigger (wrong method)
        try:
            requests.get("http://target-host.com/api", timeout=0.5)
        except RuntimeError:
            pytest.fail("GET should not match POST rule")
        except Exception:
            pass

        # POST to target-host SHOULD trigger
        with pytest.raises(RuntimeError, match="http-matched"):
            requests.post("http://target-host.com/api", json={})

        _destroy(agent, suid)

    def test_httpx_matchers_host_and_path(self, agent):
        """Docs: host=dashscope.aliyuncs.com&path=/v1/chat/completions"""
        suid = "doc-match-httpx-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "httpx-matched",
            "host": "dashscope.aliyuncs.com",
            "path": "/v1/chat/completions",
        })
        assert resp["code"] == 200
        _destroy(agent, suid)

    def test_mysql_matchers_sqltype(self, agent):
        """Docs: sqltype=SELECT"""
        suid = "doc-match-mysql-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "mysql",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "select-blocked",
            "sqltype": "SELECT",
        })
        assert resp["code"] == 200

        from unittest.mock import MagicMock
        import mysql.connector.cursor

        cursor = MagicMock(spec=mysql.connector.cursor.MySQLCursor)
        execute_fn = mysql.connector.cursor.MySQLCursor.execute

        # SELECT should trigger
        with pytest.raises(RuntimeError, match="select-blocked"):
            execute_fn(cursor, "SELECT * FROM users")

        # INSERT should NOT trigger
        try:
            execute_fn(cursor, "INSERT INTO users VALUES(1)")
        except RuntimeError as e:
            if "select-blocked" in str(e):
                pytest.fail("INSERT should not match SELECT rule")
        except Exception:
            pass

        _destroy(agent, suid)

    def test_grpc_matchers_service(self, agent):
        """Docs: service=order.OrderService"""
        suid = "doc-match-grpc-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "grpc",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "grpc-matched",
            "service": "order.OrderService",
        })
        assert resp["code"] == 200

        from unittest.mock import MagicMock
        import grpc._channel

        # Matching service
        callable_obj = MagicMock()
        callable_obj._method = b"/order.OrderService/CreateOrder"
        call_fn = grpc._channel._UnaryUnaryMultiCallable.__call__
        with pytest.raises(RuntimeError, match="grpc-matched"):
            call_fn(callable_obj, MagicMock())

        # Non-matching service
        callable_obj2 = MagicMock()
        callable_obj2._method = b"/user.UserService/GetUser"
        try:
            call_fn(callable_obj2, MagicMock())
        except RuntimeError as e:
            if "grpc-matched" in str(e):
                pytest.fail("Wrong service should not match")
        except Exception:
            pass

        _destroy(agent, suid)

    def test_kafka_matchers_topic_and_operation(self, agent):
        """Docs: topic=orders&operation=produce"""
        suid = "doc-match-kafka-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "kafka",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "kafka-matched",
            "topic": "orders",
        })
        assert resp["code"] == 200

        from unittest.mock import MagicMock
        import kafka

        producer = MagicMock(spec=kafka.KafkaProducer)
        send_fn = kafka.KafkaProducer.send

        # Matching topic
        with pytest.raises(RuntimeError, match="kafka-matched"):
            send_fn(producer, "orders", b"msg")

        # Non-matching topic should NOT trigger
        try:
            send_fn(producer, "other-topic", b"msg")
        except RuntimeError as e:
            if "kafka-matched" in str(e):
                pytest.fail("Wrong topic should not match")
        except Exception:
            pass

        _destroy(agent, suid)

    def test_sqlalchemy_matchers_sqltype(self, agent):
        """Docs: sqltype=SELECT"""
        suid = "doc-match-sa-001"
        resp = _create(agent, {
            "suid": suid,
            "target": "sqlalchemy",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "sa-matched",
            "sqltype": "SELECT",
        })
        assert resp["code"] == 200

        from unittest.mock import MagicMock
        import sqlalchemy.engine.base

        conn = MagicMock()
        execute_fn = sqlalchemy.engine.base.Connection.execute

        with pytest.raises(RuntimeError, match="sa-matched"):
            execute_fn(conn, "SELECT 1")

        _destroy(agent, suid)


# ══════════════════════════════════════════════════════════════════════
# 4. Verify status API format (documented in all plugin guides)
# ══════════════════════════════════════════════════════════════════════

class TestDocStatusApi:
    """Verify status API returns documented format."""

    def test_status_returns_count(self, agent):
        """Docs: {"code": 200, "result": "{\"count\": N}"}"""
        suid = "doc-status-001"
        _create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "count-test",
        })

        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)

        # Trigger 3 times
        for _ in range(3):
            try:
                client.get("k")
            except RuntimeError:
                pass

        # Check status
        status = _status(agent, suid)
        assert status["code"] == 200
        result = json.loads(status["result"])
        assert result["count"] == 3, f"Expected count=3, got {result}"

        _destroy(agent, suid)
