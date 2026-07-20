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

"""Tests for the built-in plugins (Redis, Requests, MySQL)."""

from __future__ import annotations

import pytest

from chaosblade.common.model.model import Model
from chaosblade.common.model.predicate_result import PredicateResult
from chaosblade.plugins.base import DefaultActionSpec, DefaultFlagSpec, DefaultPointCut
from chaosblade.plugins.default_enhancer import DefaultBeforeEnhancer
from chaosblade.plugins.redis import RedisPlugin, RedisModelSpec, _redis_matcher_extractor
from chaosblade.plugins.requests import RequestsPlugin, RequestsModelSpec, _requests_matcher_extractor
from chaosblade.plugins.mysql import MysqlPlugin, PyMysqlPlugin, MysqlModelSpec, _mysql_matcher_extractor


# ========================
# Plugin Protocol Tests
# ========================
class TestRedisPlugin:
    def test_plugin_interface(self):
        """RedisPlugin implements the Plugin Protocol."""
        plugin = RedisPlugin()
        assert plugin.get_name() == "redis"
        assert plugin.get_model_spec() is not None
        assert plugin.get_point_cut() is not None
        assert plugin.get_enhancer() is not None

    def test_point_cut(self):
        """Redis PointCut targets redis.client.Redis.execute_command."""
        plugin = RedisPlugin()
        pc = plugin.get_point_cut()
        assert pc.get_target_module() == "redis.client"
        assert pc.get_target_function() == "execute_command"
        assert pc.get_target_class() == "Redis"

    def test_model_spec_target(self):
        """RedisModelSpec target is 'redis'."""
        spec = RedisModelSpec()
        assert spec.get_target() == "redis"

    def test_model_spec_actions(self):
        """RedisModelSpec has delay, throwCustomException, returnValue actions."""
        spec = RedisModelSpec()
        assert spec.get_action_spec("delay") is not None
        assert spec.get_action_spec("throwCustomException") is not None
        assert spec.get_action_spec("returnValue") is not None
        # Alias
        assert spec.get_action_spec("exception") is not None
        assert spec.get_action_spec("return") is not None

    def test_model_spec_predicate_valid(self):
        """Predicate passes for valid model."""
        spec = RedisModelSpec()
        model = Model(target="redis", action_name="delay")
        model.action.add_flag("time", "100")
        result = spec.predicate(model)
        assert result.success

    def test_model_spec_predicate_missing_required_flag(self):
        """Predicate fails when required 'time' flag is missing."""
        spec = RedisModelSpec()
        model = Model(target="redis", action_name="delay")
        result = spec.predicate(model)
        assert not result.success
        assert "time" in result.error

    def test_model_spec_predicate_unknown_action(self):
        """Predicate fails for unknown action."""
        spec = RedisModelSpec()
        model = Model(target="redis", action_name="nonexistent")
        result = spec.predicate(model)
        assert not result.success


class TestRequestsPlugin:
    def test_plugin_interface(self):
        """RequestsPlugin implements Plugin Protocol."""
        plugin = RequestsPlugin()
        assert plugin.get_name() == "http"
        assert plugin.get_model_spec().get_target() == "http"

    def test_point_cut(self):
        """Requests PointCut targets requests.adapters.HTTPAdapter.send."""
        plugin = RequestsPlugin()
        pc = plugin.get_point_cut()
        assert pc.get_target_module() == "requests.adapters"
        assert pc.get_target_function() == "send"
        assert pc.get_target_class() == "HTTPAdapter"

    def test_model_spec_actions(self):
        """RequestsModelSpec has all three actions."""
        spec = RequestsModelSpec()
        assert spec.get_action_spec("delay") is not None
        assert spec.get_action_spec("throwCustomException") is not None
        assert spec.get_action_spec("returnValue") is not None


class TestMysqlPlugin:
    def test_mysql_plugin_interface(self):
        """MysqlPlugin implements Plugin Protocol."""
        plugin = MysqlPlugin()
        assert plugin.get_name() == "mysql"
        assert plugin.get_model_spec().get_target() == "mysql"

    def test_pymysql_plugin_interface(self):
        """PyMysqlPlugin implements Plugin Protocol."""
        plugin = PyMysqlPlugin()
        assert plugin.get_name() == "pymysql"
        assert plugin.get_point_cut().get_target_module() == "pymysql.cursors"

    def test_mysql_point_cut(self):
        """MySQL PointCut targets mysql.connector.cursor.MySQLCursor.execute."""
        plugin = MysqlPlugin()
        pc = plugin.get_point_cut()
        assert pc.get_target_module() == "mysql.connector.cursor"
        assert pc.get_target_function() == "execute"
        assert pc.get_target_class() == "MySQLCursor"


# ========================
# Matcher Extractor Tests
# ========================
class TestRedisMatcherExtractor:
    def test_extracts_cmd_and_key(self):
        """Extracts command and key from execute_command args."""
        # args in wrapper context: (self, command, key, ...)
        fake_self = object()
        result = _redis_matcher_extractor("execute_command", fake_self, (fake_self, "GET", "mykey"), {})
        assert result["cmd"] == "GET"
        assert result["key"] == "mykey"

    def test_command_uppercased(self):
        """Command is uppercased."""
        fake_self = object()
        result = _redis_matcher_extractor("execute_command", fake_self, (fake_self, "hget", "key"), {})
        assert result["cmd"] == "HGET"

    def test_no_args(self):
        """Handles empty args gracefully."""
        result = _redis_matcher_extractor("execute_command", None, (), {})
        assert result == {}


class TestRequestsMatcherExtractor:
    def test_extracts_url_and_method(self):
        """Extracts URL, method, and host from PreparedRequest."""

        class FakeRequest:
            url = "https://api.example.com/v1/users"
            method = "POST"

        fake_adapter = object()
        result = _requests_matcher_extractor("send", fake_adapter, (fake_adapter, FakeRequest()), {})
        assert result["url"] == "https://api.example.com/v1/users"
        assert result["method"] == "POST"
        assert result["host"] == "api.example.com"

    def test_no_request(self):
        """Handles missing request gracefully."""
        result = _requests_matcher_extractor("send", None, (), {})
        assert result == {}


class TestMysqlMatcherExtractor:
    def test_extracts_sql_and_type(self):
        """Extracts SQL statement and SQL type."""
        fake_cursor = object()
        result = _mysql_matcher_extractor(
            "execute", fake_cursor, (fake_cursor, "SELECT * FROM users WHERE id=1"), {}
        )
        assert result["sql"] == "SELECT * FROM users WHERE id=1"
        assert result["sqltype"] == "SELECT"

    def test_extracts_insert(self):
        """Extracts INSERT SQL type."""
        fake_cursor = object()
        result = _mysql_matcher_extractor(
            "execute", fake_cursor, (fake_cursor, "INSERT INTO logs VALUES (1)"), {}
        )
        assert result["sqltype"] == "INSERT"

    def test_extracts_database(self):
        """Extracts database name from cursor.connection.database."""

        class FakeConnection:
            database = "mydb"

        class FakeCursor:
            connection = FakeConnection()

        cursor = FakeCursor()
        result = _mysql_matcher_extractor(
            "execute", cursor, (cursor, "SELECT 1"), {}
        )
        assert result["database"] == "mydb"


# ========================
# DefaultBeforeEnhancer Tests
# ========================
class TestDefaultBeforeEnhancer:
    def test_builds_enhancer_model_with_method(self):
        """Always includes method name in matchers."""
        enhancer = DefaultBeforeEnhancer(target="test")
        model = enhancer.do_before_advice("test", "some_method", None, (), {})
        assert model is not None
        assert model.matcher_model.get("method") == "some_method"

    def test_builds_with_extractor(self):
        """Uses extractor to add additional matchers."""
        def extractor(method, obj, args, kwargs):
            return {"custom_key": "custom_value"}

        enhancer = DefaultBeforeEnhancer(target="test", extractor=extractor)
        model = enhancer.do_before_advice("test", "func", None, (), {})
        assert model.matcher_model.get("custom_key") == "custom_value"

    def test_extractor_error_handled(self):
        """Extractor errors don't crash - returns model without extra matchers."""
        def bad_extractor(method, obj, args, kwargs):
            raise ValueError("extraction failed")

        enhancer = DefaultBeforeEnhancer(target="test", extractor=bad_extractor)
        model = enhancer.do_before_advice("test", "func", None, (), {})
        assert model is not None
        assert model.matcher_model.get("method") == "func"
