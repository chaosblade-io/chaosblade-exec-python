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

"""Tests for StatusManager and StatusMetric."""

import threading

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.center.status_manager import StatusMetric
from chaosblade.common.model.model import Model


class TestStatusMetric:
    def test_increase(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)
        assert metric.count == 0
        metric.increase()
        assert metric.count == 1
        metric.increase()
        assert metric.count == 2

    def test_decrease(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)
        metric.increase()
        metric.increase()
        metric.decrease()
        assert metric.count == 1

    def test_decrease_at_zero(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)
        metric.decrease()
        assert metric.count == 0  # Should not go negative

    def test_increase_with_lock_under_limit(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)
        assert metric.increase_with_lock(3) is True
        assert metric.increase_with_lock(3) is True
        assert metric.increase_with_lock(3) is True
        assert metric.count == 3

    def test_increase_with_lock_at_limit(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)
        metric.increase_with_lock(2)
        metric.increase_with_lock(2)
        assert metric.increase_with_lock(2) is False
        assert metric.count == 2

    def test_thread_safety(self):
        model = Model("redis", "delay")
        metric = StatusMetric(model)

        def inc():
            for _ in range(100):
                metric.increase()

        threads = [threading.Thread(target=inc) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert metric.count == 1000


class TestStatusManager:
    def test_register_and_exists(self):
        sm = ManagerFactory.get_status_manager()
        model = Model("redis", "delay")
        result = sm.register_exp("uid1", model)
        assert result.success is True
        assert sm.exp_exists("redis") is True
        assert sm.exp_exists("flask") is False

    def test_duplicate_registration(self):
        sm = ManagerFactory.get_status_manager()
        model = Model("redis", "delay")
        sm.register_exp("uid1", model)
        result = sm.register_exp("uid1", model)
        assert result.success is False
        assert "already exists" in result.message

    def test_remove_exp(self):
        sm = ManagerFactory.get_status_manager()
        model = Model("redis", "delay")
        sm.register_exp("uid1", model)
        removed = sm.remove_exp("uid1")
        assert removed is not None
        assert removed.target == "redis"
        assert sm.exp_exists("redis") is False

    def test_remove_nonexistent(self):
        sm = ManagerFactory.get_status_manager()
        assert sm.remove_exp("nonexist") is None

    def test_get_exp_by_target(self):
        sm = ManagerFactory.get_status_manager()
        sm.register_exp("uid1", Model("redis", "delay"))
        sm.register_exp("uid2", Model("redis", "exception"))
        sm.register_exp("uid3", Model("flask", "delay"))

        redis_exps = sm.get_exp_by_target("redis")
        assert len(redis_exps) == 2
        flask_exps = sm.get_exp_by_target("flask")
        assert len(flask_exps) == 1

    def test_get_status_metric_by_uid(self):
        sm = ManagerFactory.get_status_manager()
        sm.register_exp("uid1", Model("redis", "delay"))
        metric = sm.get_status_metric_by_uid("uid1")
        assert metric is not None
        assert metric.model.target == "redis"
        assert sm.get_status_metric_by_uid("nonexist") is None

    def test_list_uids(self):
        sm = ManagerFactory.get_status_manager()
        sm.register_exp("uid1", Model("redis", "delay"))
        sm.register_exp("uid2", Model("redis", "exception"))
        sm.register_exp("uid3", Model("redis", "delay"))

        uids = sm.list_uids("redis", "delay")
        assert uids == {"uid1", "uid3"}

    def test_unload(self):
        sm = ManagerFactory.get_status_manager()
        sm.register_exp("uid1", Model("redis", "delay"))
        sm.unload()
        assert sm.exp_exists("redis") is False
        assert sm.get_all_uids() == set()
