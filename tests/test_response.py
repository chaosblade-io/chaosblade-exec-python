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

"""Tests for Response and Code."""

import json

from chaosblade.common.transport.response import Code, Response


class TestCode:
    def test_values(self):
        assert Code.OK == 200
        assert Code.NOT_FOUND == 404
        assert Code.ILLEGAL_PARAMETER == 405
        assert Code.DUPLICATE_INJECTION == 406
        assert Code.SERVER_ERROR == 500
        assert Code.ILLEGAL_STATE == 504


class TestResponse:
    def test_of_success(self):
        resp = Response.of_success("hello")
        assert resp.code == 200
        assert resp.success is True
        assert resp.result == "hello"
        assert resp.error is None

    def test_of_failure(self):
        resp = Response.of_failure(Code.NOT_FOUND, "not found")
        assert resp.code == 404
        assert resp.success is False
        assert resp.error == "not found"
        assert resp.result is None

    def test_to_dict_success(self):
        resp = Response.of_success("ok")
        d = resp.to_dict()
        assert d == {"code": 200, "success": True, "result": "ok"}

    def test_to_dict_failure(self):
        resp = Response.of_failure(Code.SERVER_ERROR, "boom")
        d = resp.to_dict()
        assert d == {"code": 500, "success": False, "error": "boom"}

    def test_to_json(self):
        resp = Response.of_success("test")
        parsed = json.loads(resp.to_json())
        assert parsed["code"] == 200
        assert parsed["success"] is True
        assert parsed["result"] == "test"


class TestResponseSerialization:
    """Response serialization with various result types."""

    def test_of_success_with_dict(self):
        resp = Response.of_success({"key": "value"})
        assert resp.success is True
        data = json.loads(resp.to_json())
        assert data["result"] == {"key": "value"}

    def test_of_success_with_list(self):
        resp = Response.of_success([1, 2, 3])
        data = json.loads(resp.to_json())
        assert data["result"] == [1, 2, 3]

    def test_of_success_with_string(self):
        resp = Response.of_success("hello")
        data = json.loads(resp.to_json())
        assert data["result"] == "hello"

    def test_of_success_with_nested_dict(self):
        result = {"experiments": [{"uid": "a1", "target": "redis"}]}
        resp = Response.of_success(result)
        data = json.loads(resp.to_json())
        assert data["result"]["experiments"][0]["uid"] == "a1"

    def test_to_json_default_str_fallback(self):
        """Non-serializable values fall back to str()."""
        resp = Response.of_success({"obj": object()})
        # Should not raise - uses default=str
        result = resp.to_json()
        assert "result" in result
