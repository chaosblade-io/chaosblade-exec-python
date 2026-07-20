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

"""Tests for Task 5 plugins (gRPC, Kafka, SQLAlchemy) and safety features."""

from __future__ import annotations

import pytest

from chaosblade.common.injection.injector import Injector
from chaosblade.common.model.model import Model
from chaosblade.plugins.grpc import GrpcPlugin, GrpcModelSpec, _grpc_matcher_extractor
from chaosblade.plugins.kafka import (
    KafkaProducerPlugin,
    KafkaConsumerPlugin,
    KafkaModelSpec,
    _kafka_producer_matcher_extractor,
    _kafka_consumer_matcher_extractor,
)
from chaosblade.plugins.sqlalchemy import (
    SqlalchemyPlugin,
    SqlalchemyModelSpec,
    _sqlalchemy_matcher_extractor,
)


# ========================
# gRPC Plugin Tests
# ========================
class TestGrpcPlugin:
    def test_plugin_interface(self):
        plugin = GrpcPlugin()
        assert plugin.get_name() == "grpc"
        assert plugin.get_model_spec().get_target() == "grpc"
        assert plugin.get_point_cut().get_target_module() == "grpc._channel"
        assert plugin.get_point_cut().get_target_function() == "__call__"
        assert plugin.get_point_cut().get_target_class() == "_UnaryUnaryMultiCallable"

    def test_model_spec_actions(self):
        spec = GrpcModelSpec()
        assert spec.get_action_spec("delay") is not None
        assert spec.get_action_spec("throwCustomException") is not None
        assert spec.get_action_spec("exception") is not None  # alias

    def test_matcher_extractor_with_string_method(self):
        """Extract matchers from gRPC callable with string _method."""
        class FakeCallable:
            _method = "/com.example.UserService/GetUser"

        result = _grpc_matcher_extractor("__call__", FakeCallable(), (), {})
        assert result["method"] == "/com.example.UserService/GetUser"
        assert result["service"] == "com.example.UserService"

    def test_matcher_extractor_with_bytes_method(self):
        """Extract matchers from gRPC callable with bytes _method."""
        class FakeCallable:
            _method = b"/com.example.OrderService/CreateOrder"

        result = _grpc_matcher_extractor("__call__", FakeCallable(), (), {})
        assert result["method"] == "/com.example.OrderService/CreateOrder"
        assert result["service"] == "com.example.OrderService"

    def test_matcher_extractor_no_obj(self):
        result = _grpc_matcher_extractor("__call__", None, (), {})
        assert result == {}


# ========================
# Kafka Plugin Tests
# ========================
class TestKafkaPlugin:
    def test_producer_plugin_interface(self):
        plugin = KafkaProducerPlugin()
        assert plugin.get_name() == "kafka-producer"
        assert plugin.get_model_spec().get_target() == "kafka"
        assert plugin.get_point_cut().get_target_function() == "send"
        assert plugin.get_point_cut().get_target_class() == "KafkaProducer"

    def test_consumer_plugin_interface(self):
        plugin = KafkaConsumerPlugin()
        assert plugin.get_name() == "kafka-consumer"
        assert plugin.get_point_cut().get_target_function() == "poll"
        assert plugin.get_point_cut().get_target_class() == "KafkaConsumer"

    def test_producer_extractor(self):
        """Extract topic from send args."""
        fake_self = object()
        result = _kafka_producer_matcher_extractor("send", fake_self, (fake_self, "orders"), {})
        assert result["topic"] == "orders"
        assert result["operation"] == "produce"

    def test_producer_extractor_kwargs(self):
        """Extract topic from kwargs."""
        fake_self = object()
        result = _kafka_producer_matcher_extractor("send", fake_self, (fake_self,), {"topic": "events"})
        assert result["topic"] == "events"

    def test_consumer_extractor_with_subscription(self):
        """Extract topics from consumer subscription."""
        class FakeConsumer:
            _subscription = None
            subscription = {"orders", "events"}

        consumer = FakeConsumer()
        result = _kafka_consumer_matcher_extractor("poll", consumer, (consumer,), {})
        assert result["operation"] == "consume"
        # topics should be comma-joined (order may vary due to set)
        assert "orders" in result.get("topic", "")
        assert "events" in result.get("topic", "")


# ========================
# SQLAlchemy Plugin Tests
# ========================
class TestSqlalchemyPlugin:
    def test_plugin_interface(self):
        plugin = SqlalchemyPlugin()
        assert plugin.get_name() == "sqlalchemy"
        assert plugin.get_model_spec().get_target() == "sqlalchemy"
        assert plugin.get_point_cut().get_target_module() == "sqlalchemy.engine.base"
        assert plugin.get_point_cut().get_target_function() == "execute"
        assert plugin.get_point_cut().get_target_class() == "Connection"

    def test_model_spec_actions(self):
        spec = SqlalchemyModelSpec()
        assert spec.get_action_spec("delay") is not None
        assert spec.get_action_spec("throwCustomException") is not None
        assert spec.get_action_spec("returnValue") is not None

    def test_matcher_extractor(self):
        """Extract SQL statement and type."""
        fake_conn = object()
        result = _sqlalchemy_matcher_extractor(
            "execute", fake_conn, (fake_conn, "SELECT * FROM users"), {}
        )
        assert result["sql"] == "SELECT * FROM users"
        assert result["sqltype"] == "SELECT"

    def test_matcher_extractor_insert(self):
        fake_conn = object()
        result = _sqlalchemy_matcher_extractor(
            "execute", fake_conn, (fake_conn, "INSERT INTO logs VALUES (1)"), {}
        )
        assert result["sqltype"] == "INSERT"

    def test_matcher_extractor_with_engine(self):
        """Extract database backend from engine URL."""
        class FakeUrl:
            drivername = "postgresql+psycopg2"

        class FakeEngine:
            url = FakeUrl()

        class FakeConnection:
            engine = FakeEngine()

        conn = FakeConnection()
        result = _sqlalchemy_matcher_extractor(
            "execute", conn, (conn, "SELECT 1"), {}
        )
        assert result["database"] == "postgresql+psycopg2"


# ========================
# Injector Safety Tests
# ========================
class TestInjectorSafety:
    def setup_method(self):
        """Ensure injector is enabled before each test."""
        Injector.set_enabled(True)

    def teardown_method(self):
        Injector.set_enabled(True)

    def test_global_switch_disable(self):
        """When disabled, inject() is a no-op."""
        Injector.set_enabled(False)
        assert not Injector.is_enabled()

        # This should not raise or do anything
        from chaosblade.common.model.enhancer_model import EnhancerModel
        em = EnhancerModel()
        em.target = "redis"
        # Should return without error (no InterruptProcessException)
        Injector.inject(em)

    def test_global_switch_enable(self):
        """Default state is enabled."""
        assert Injector.is_enabled()

    def test_global_switch_toggle(self):
        """Can toggle enabled state."""
        Injector.set_enabled(False)
        assert not Injector.is_enabled()
        Injector.set_enabled(True)
        assert Injector.is_enabled()
