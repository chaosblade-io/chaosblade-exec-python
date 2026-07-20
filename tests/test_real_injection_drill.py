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

"""Real Fault Injection Drill - End-to-End Verification.

This script starts a REAL ChaosBladeAgent embedded in-process, creates experiments
via the HTTP API, then invokes real middleware client calls to verify that fault
injection actually works at the library-level.

Verified capabilities:
- 6 middleware plugins × 3 fault types = 18 injection scenarios
  (redis, http, mysql, pymysql, grpc, kafka-producer, kafka-consumer, sqlalchemy)
- 2 directly injection executors (CpuBurn, MemoryFill)
- Matcher-based filtering (positive + negative cases)
- Experiment lifecycle (create → verify → destroy → confirm clean)

Prerequisite:
  pip install redis requests mysql-connector-python pymysql grpcio kafka-python sqlalchemy
  (No real backend servers are needed — injections intercept BEFORE network calls)
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse

import pytest

# ──────────────────────────────────────────────────────────────────────
# Override conftest's autouse reset_managers fixture (we manage lifecycle ourselves)
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


def _api_create(base_url: str, params: dict) -> dict:
    """Send a create request to the agent API."""
    url = f"{base_url}/create?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _api_destroy(base_url: str, suid: str) -> dict:
    """Send a destroy request to the agent API."""
    url = f"{base_url}/destroy?suid={suid}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


# ──────────────────────────────────────────────────────────────────────
# 1. Redis Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestRedisInjection:
    """Verify Redis fault injection: delay, exception, returnValue."""

    def test_redis_throw_exception(self, agent):
        """Inject exception into Redis GET command."""
        suid = "redis-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "ConnectionError",
            "exception-message": "chaos: redis connection refused",
            "cmd": "GET",
        })
        assert resp["code"] == 200, f"Create failed: {resp}"

        try:
            import redis
            client = redis.Redis(host="127.0.0.1", port=16379)  # fake port
            with pytest.raises(ConnectionError, match="chaos: redis connection refused"):
                client.get("test-key")
        finally:
            _api_destroy(agent, suid)

    def test_redis_return_value(self, agent):
        """Inject custom return value into Redis GET command."""
        suid = "redis-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "returnValue",
            "return-value": "fake-cached-data",
            "cmd": "GET",
        })
        assert resp["code"] == 200, f"Create failed: {resp}"

        try:
            import redis
            client = redis.Redis(host="127.0.0.1", port=16379)
            result = client.get("any-key")
            assert result == "fake-cached-data"
        finally:
            _api_destroy(agent, suid)

    def test_redis_delay(self, agent):
        """Inject 200ms delay into Redis SET command."""
        suid = "redis-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "delay",
            "time": "200",
            "cmd": "SET",
        })
        assert resp["code"] == 200, f"Create failed: {resp}"

        try:
            import redis
            client = redis.Redis(host="127.0.0.1", port=16379)
            start = time.time()
            try:
                client.set("k", "v")
            except Exception:
                pass  # Connection will fail after delay since no real server
            elapsed = time.time() - start
            # Delay should have been injected (≥ 200ms)
            assert elapsed >= 0.18, f"Expected ≥200ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)

    def test_redis_matcher_filter(self, agent):
        """Verify matcher only applies to matching commands."""
        suid = "redis-filter-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "injected",
            "cmd": "HGET",  # Only match HGET
        })
        assert resp["code"] == 200

        try:
            import redis
            client = redis.Redis(host="127.0.0.1", port=16379)
            # GET should NOT be affected (different cmd)
            try:
                client.get("key")  # Should try real connection, not be intercepted
            except ConnectionRefusedError:
                pass  # Expected: no injection, real connection fails
            except redis.exceptions.ConnectionError:
                pass  # Also acceptable: real connection refused
            except RuntimeError:
                pytest.fail("GET should NOT have been intercepted by HGET rule")
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 2. HTTP/Requests Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestHttpInjection:
    """Verify HTTP (requests library) fault injection."""

    def test_http_throw_exception(self, agent):
        """Inject ConnectionError into HTTP requests."""
        suid = "http-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "http",
            "action": "throwCustomException",
            "exception": "ConnectionError",
            "exception-message": "chaos: network unreachable",
        })
        assert resp["code"] == 200

        try:
            import requests
            with pytest.raises(ConnectionError, match="chaos: network unreachable"):
                requests.get("http://fake-service.local/api/data")
        finally:
            _api_destroy(agent, suid)

    def test_http_return_value(self, agent):
        """Inject custom return value for HTTP requests."""
        suid = "http-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "http",
            "action": "returnValue",
            "return-value": '{"status": "mocked"}',
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import requests.adapters

            # Test at the adapter level (Session.send adds post-processing that
            # expects a real Response object, so we bypass it)
            adapter = requests.adapters.HTTPAdapter()
            prep = MagicMock()
            prep.url = "http://fake-service.local/api/health"
            prep.method = "GET"

            send_fn = requests.adapters.HTTPAdapter.send
            result = send_fn(adapter, prep)
            assert result == {"status": "mocked"}
        finally:
            _api_destroy(agent, suid)

    def test_http_delay(self, agent):
        """Inject 300ms delay into HTTP requests."""
        suid = "http-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "http",
            "action": "delay",
            "time": "300",
        })
        assert resp["code"] == 200

        try:
            import requests
            start = time.time()
            try:
                requests.get("http://fake-service.local/api", timeout=1)
            except Exception:
                pass  # Connection will fail after delay
            elapsed = time.time() - start
            assert elapsed >= 0.28, f"Expected ≥300ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)

    def test_http_matcher_by_host(self, agent):
        """Verify host-based matcher filtering."""
        suid = "http-host-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "http",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: targeted host",
            "host": "target-host.com",
        })
        assert resp["code"] == 200

        try:
            import requests
            # Request to different host should NOT be intercepted
            try:
                requests.get("http://other-host.com/api", timeout=0.5)
            except RuntimeError:
                pytest.fail("Request to other-host should NOT be intercepted")
            except Exception:
                pass  # Connection failure expected

            # Request to target host SHOULD be intercepted
            with pytest.raises(RuntimeError, match="chaos: targeted host"):
                requests.get("http://target-host.com/api")
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 3. MySQL Plugin Verification (mysql-connector-python)
# ──────────────────────────────────────────────────────────────────────

class TestMysqlInjection:
    """Verify MySQL (mysql-connector-python) fault injection."""

    def test_mysql_throw_exception(self, agent):
        """Inject OperationalError into MySQL cursor.execute."""
        suid = "mysql-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "mysql",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: database unavailable",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import mysql.connector.cursor

            # Create a mock cursor to avoid needing a real MySQL connection
            cursor = MagicMock(spec=mysql.connector.cursor.MySQLCursor)
            # Manually call the patched execute
            execute_fn = mysql.connector.cursor.MySQLCursor.execute
            with pytest.raises(RuntimeError, match="chaos: database unavailable"):
                execute_fn(cursor, "SELECT 1")
        finally:
            _api_destroy(agent, suid)

    def test_mysql_return_value(self, agent):
        """Inject custom return value for MySQL queries."""
        suid = "mysql-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "mysql",
            "action": "returnValue",
            "return-value": "[]",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import mysql.connector.cursor

            cursor = MagicMock(spec=mysql.connector.cursor.MySQLCursor)
            execute_fn = mysql.connector.cursor.MySQLCursor.execute
            result = execute_fn(cursor, "SELECT * FROM users")
            assert result == []
        finally:
            _api_destroy(agent, suid)

    def test_mysql_delay(self, agent):
        """Inject 150ms delay into MySQL queries."""
        suid = "mysql-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "mysql",
            "action": "delay",
            "time": "150",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import mysql.connector.cursor

            cursor = MagicMock()
            # Configure mock to satisfy the original execute() internals
            cursor._connection = MagicMock()
            cursor._connection.database = "test_db"

            execute_fn = mysql.connector.cursor.MySQLCursor.execute
            start = time.time()
            try:
                execute_fn(cursor, "SELECT 1")
            except Exception:
                pass  # Original may fail on mock; timing is what matters
            elapsed = time.time() - start
            assert elapsed >= 0.13, f"Expected ≥150ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 4. PyMySQL Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestPyMysqlInjection:
    """Verify PyMySQL fault injection."""

    def test_pymysql_throw_exception(self, agent):
        """Inject exception into PyMySQL cursor.execute."""
        suid = "pymysql-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "mysql",  # PyMySQL shares the "mysql" target
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: pymysql fault",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import pymysql.cursors

            cursor = MagicMock(spec=pymysql.cursors.Cursor)
            execute_fn = pymysql.cursors.Cursor.execute
            with pytest.raises(RuntimeError, match="chaos: pymysql fault"):
                execute_fn(cursor, "INSERT INTO t VALUES(1)")
        finally:
            _api_destroy(agent, suid)

    def test_pymysql_return_value(self, agent):
        """Inject return value into PyMySQL cursor.execute."""
        suid = "pymysql-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "mysql",
            "action": "returnValue",
            "return-value": "0",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import pymysql.cursors

            cursor = MagicMock(spec=pymysql.cursors.Cursor)
            execute_fn = pymysql.cursors.Cursor.execute
            result = execute_fn(cursor, "UPDATE t SET x=1")
            assert result == 0
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 5. gRPC Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestGrpcInjection:
    """Verify gRPC fault injection."""

    def test_grpc_throw_exception(self, agent):
        """Inject exception into gRPC unary-unary calls."""
        suid = "grpc-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "grpc",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: grpc unavailable",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock, patch
            import grpc._channel

            # Create a mock _UnaryUnaryMultiCallable
            callable_obj = MagicMock()
            callable_obj._method = b"/test.Service/GetData"

            # Get the patched __call__
            call_fn = grpc._channel._UnaryUnaryMultiCallable.__call__
            with pytest.raises(RuntimeError, match="chaos: grpc unavailable"):
                call_fn(callable_obj, MagicMock())  # (self, request)
        finally:
            _api_destroy(agent, suid)

    def test_grpc_return_value(self, agent):
        """Inject custom return value for gRPC calls."""
        suid = "grpc-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "grpc",
            "action": "returnValue",
            "return-value": '{"result": "mock"}',
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import grpc._channel

            callable_obj = MagicMock()
            callable_obj._method = b"/test.Service/GetData"

            call_fn = grpc._channel._UnaryUnaryMultiCallable.__call__
            result = call_fn(callable_obj, MagicMock())
            assert result == {"result": "mock"}
        finally:
            _api_destroy(agent, suid)

    def test_grpc_delay(self, agent):
        """Inject 100ms delay into gRPC calls."""
        suid = "grpc-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "grpc",
            "action": "delay",
            "time": "100",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import grpc._channel

            callable_obj = MagicMock()
            callable_obj._method = b"/test.Service/Call"

            call_fn = grpc._channel._UnaryUnaryMultiCallable.__call__
            start = time.time()
            try:
                call_fn(callable_obj, MagicMock())
            except Exception:
                pass
            elapsed = time.time() - start
            assert elapsed >= 0.08, f"Expected ≥100ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 6. Kafka Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestKafkaInjection:
    """Verify Kafka producer/consumer fault injection."""

    def test_kafka_producer_throw_exception(self, agent):
        """Inject exception into KafkaProducer.send."""
        suid = "kafka-prod-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "kafka",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: broker unavailable",
            "topic": "orders",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock, patch
            import kafka

            # Mock KafkaProducer to avoid real connection
            producer = MagicMock(spec=kafka.KafkaProducer)
            send_fn = kafka.KafkaProducer.send
            with pytest.raises(RuntimeError, match="chaos: broker unavailable"):
                send_fn(producer, "orders", b"msg")
        finally:
            _api_destroy(agent, suid)

    def test_kafka_producer_return_value(self, agent):
        """Inject return value into KafkaProducer.send."""
        suid = "kafka-prod-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "kafka",
            "action": "returnValue",
            "return-value": "null",
            "topic": "events",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import kafka

            producer = MagicMock(spec=kafka.KafkaProducer)
            send_fn = kafka.KafkaProducer.send
            result = send_fn(producer, "events", b"data")
            assert result is None
        finally:
            _api_destroy(agent, suid)

    def test_kafka_consumer_throw_exception(self, agent):
        """Inject exception into KafkaConsumer.poll."""
        suid = "kafka-cons-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "kafka",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: consumer timeout",
            "operation": "consume",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import kafka

            consumer = MagicMock(spec=kafka.KafkaConsumer)
            poll_fn = kafka.KafkaConsumer.poll
            with pytest.raises(RuntimeError, match="chaos: consumer timeout"):
                poll_fn(consumer)
        finally:
            _api_destroy(agent, suid)

    def test_kafka_producer_delay(self, agent):
        """Inject 120ms delay into Kafka produce."""
        suid = "kafka-prod-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "kafka",
            "action": "delay",
            "time": "120",
            "topic": "logs",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import kafka

            producer = MagicMock(spec=kafka.KafkaProducer)
            send_fn = kafka.KafkaProducer.send
            start = time.time()
            try:
                send_fn(producer, "logs", b"entry")
            except Exception:
                pass
            elapsed = time.time() - start
            assert elapsed >= 0.10, f"Expected ≥120ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 7. SQLAlchemy Plugin Verification
# ──────────────────────────────────────────────────────────────────────

class TestSqlalchemyInjection:
    """Verify SQLAlchemy fault injection."""

    def test_sqlalchemy_throw_exception(self, agent):
        """Inject exception into SQLAlchemy Connection.execute."""
        suid = "sa-exc-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "sqlalchemy",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "chaos: db connection pool exhausted",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import sqlalchemy.engine.base

            conn = MagicMock()
            execute_fn = sqlalchemy.engine.base.Connection.execute
            with pytest.raises(RuntimeError, match="chaos: db connection pool exhausted"):
                execute_fn(conn, "SELECT 1")
        finally:
            _api_destroy(agent, suid)

    def test_sqlalchemy_return_value(self, agent):
        """Inject return value into SQLAlchemy queries."""
        suid = "sa-ret-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "sqlalchemy",
            "action": "returnValue",
            "return-value": "[]",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import sqlalchemy.engine.base

            conn = MagicMock()
            execute_fn = sqlalchemy.engine.base.Connection.execute
            result = execute_fn(conn, "SELECT * FROM orders")
            assert result == []
        finally:
            _api_destroy(agent, suid)

    def test_sqlalchemy_delay(self, agent):
        """Inject 180ms delay into SQLAlchemy queries."""
        suid = "sa-delay-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "sqlalchemy",
            "action": "delay",
            "time": "180",
        })
        assert resp["code"] == 200

        try:
            from unittest.mock import MagicMock
            import sqlalchemy.engine.base

            conn = MagicMock()
            execute_fn = sqlalchemy.engine.base.Connection.execute
            start = time.time()
            try:
                execute_fn(conn, "SELECT 1")
            except Exception:
                pass
            elapsed = time.time() - start
            assert elapsed >= 0.16, f"Expected ≥180ms delay, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 8. Directly Injection Verification (CPU / Memory)
# ──────────────────────────────────────────────────────────────────────

class TestDirectlyInjection:
    """Verify DirectlyInjection executors (CpuBurn, MemoryFill)."""

    def test_cpu_burn_create_destroy(self):
        """Verify CPU burn starts workers and stops cleanly."""
        from chaosblade.executor.directly_executors import CpuBurnExecutor
        from chaosblade.common.model.model import Model

        executor = CpuBurnExecutor()
        model = Model("cpu", "cpuBurn")
        model.action.add_flag("cpu-count", "1")
        model.action.add_flag("cpu-percent", "50")

        executor.create_injection("cpu-001", model)
        assert len(executor._workers) == 1
        assert executor._running is True

        time.sleep(0.2)  # Let it burn briefly

        executor.destroy_injection("cpu-001", model)
        assert executor._running is False
        assert len(executor._workers) == 0

    def test_memory_fill_create_destroy(self):
        """Verify memory fill allocates and releases."""
        from chaosblade.executor.directly_executors import MemoryFillExecutor
        from chaosblade.common.model.model import Model

        executor = MemoryFillExecutor()
        model = Model("mem", "memFill")
        model.action.add_flag("mem-size", "2")  # 2MB

        executor.create_injection("mem-001", model)
        assert len(executor._allocated) > 0
        total_bytes = sum(len(chunk) for chunk in executor._allocated)
        assert total_bytes >= 2 * 1024 * 1024

        executor.destroy_injection("mem-001", model)
        assert len(executor._allocated) == 0


# ──────────────────────────────────────────────────────────────────────
# 9. Experiment Lifecycle Verification
# ──────────────────────────────────────────────────────────────────────

class TestExperimentLifecycle:
    """Verify full experiment lifecycle: create → active → destroy → clean."""

    def test_create_destroy_cycle(self, agent):
        """After destroy, injection should no longer apply."""
        suid = "lifecycle-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "active-fault",
            "cmd": "GET",
        })
        assert resp["code"] == 200

        import redis
        client = redis.Redis(host="127.0.0.1", port=16379)

        # Fault should be active
        with pytest.raises(RuntimeError, match="active-fault"):
            client.get("k")

        # Destroy experiment
        d_resp = _api_destroy(agent, suid)
        assert d_resp["code"] == 200

        # Fault should be gone — now we get real connection error
        with pytest.raises(Exception) as exc_info:
            client.get("k")
        # Should NOT be our RuntimeError anymore
        assert "active-fault" not in str(exc_info.value)

    def test_duplicate_suid_rejected(self, agent):
        """Creating an experiment with same suid should fail."""
        suid = "dup-test-001"
        params = {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "test",
        }
        resp1 = _api_create(agent, params)
        assert resp1["code"] == 200

        try:
            resp2 = _api_create(agent, params)
            # Should be rejected as duplicate
            assert resp2["code"] != 200
        finally:
            _api_destroy(agent, suid)

    def test_status_query(self, agent):
        """Status API should return active experiments."""
        suid = "status-test-001"
        _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "returnValue",
            "return-value": "ok",
        })
        try:
            # Status API requires suid parameter
            url = f"{agent}/status?suid={suid}"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            assert data["code"] == 200
            result = json.loads(data["result"])
            assert "count" in result
        finally:
            _api_destroy(agent, suid)


# ──────────────────────────────────────────────────────────────────────
# 10. Advanced: Effect-count limiting
# ──────────────────────────────────────────────────────────────────────

class TestEffectLimiting:
    """Verify effect-count and effect-percent limiting."""

    def test_effect_count_limit(self, agent):
        """Injection should only apply N times with effect-count."""
        suid = "limit-count-001"
        resp = _api_create(agent, {
            "suid": suid,
            "target": "redis",
            "action": "throwCustomException",
            "exception": "RuntimeError",
            "exception-message": "limited-fault",
            "effect-count": "2",
        })
        assert resp["code"] == 200

        try:
            import redis
            client = redis.Redis(host="127.0.0.1", port=16379)

            # First 2 calls should raise
            for _ in range(2):
                with pytest.raises(RuntimeError, match="limited-fault"):
                    client.get("key")

            # 3rd call should NOT raise (limit reached)
            with pytest.raises(Exception) as exc_info:
                client.get("key")
            assert "limited-fault" not in str(exc_info.value)
        finally:
            _api_destroy(agent, suid)
