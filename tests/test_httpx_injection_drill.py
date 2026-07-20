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

"""End-to-end verification: httpx plugin fault injection for LLM call scenarios.

This test file verifies that chaosblade-exec-python can intercept httpx-based
HTTP calls (the transport used by langchain-openai / openai SDK / DashScope router)
and inject delay, exception, and return-value faults.

The tests simulate the exact call pattern used by ai-testing-platform's LLM service.
"""

from __future__ import annotations

import asyncio
import json
import time
from urllib.parse import urljoin

import httpx
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_managers():
    """No-op override: the module-scoped agent fixture manages lifecycle."""
    yield


@pytest.fixture(scope="module")
def agent():
    """Start a ChaosBlade agent for the duration of this module."""
    from chaosblade.bootstrap.agent import ChaosBladeAgent

    agent = ChaosBladeAgent(port=0, host="127.0.0.1")
    agent.start()
    port = agent._server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    agent.stop()


def _api_create(agent: str, params: dict) -> dict:
    """Send /create to the agent and return parsed JSON response."""
    import urllib.request
    import urllib.parse

    url = f"{agent}/create?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _api_destroy(agent: str, suid: str) -> dict:
    """Send /destroy to the agent."""
    import urllib.request

    url = f"{agent}/destroy?suid={suid}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _api_status(agent: str, suid: str) -> dict:
    """Query experiment status."""
    import urllib.request

    url = f"{agent}/status?suid={suid}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# A simple echo server to receive httpx requests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def echo_server():
    """Start a simple HTTP echo server for testing httpx calls."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    class EchoHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            # Simulate DashScope OpenAI-compatible response
            response = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! I am a test LLM response."
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            }
            resp_bytes = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        def do_GET(self):
            response = {"status": "ok"}
            resp_bytes = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)

        def log_message(self, format, *args):
            pass  # Suppress log output

    server = HTTPServer(("127.0.0.1", 0), EchoHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ---------------------------------------------------------------------------
# Test: httpx exception injection (simulating LLM call failure)
# ---------------------------------------------------------------------------


class TestHttpxExceptionInjection:
    """Verify exception injection on httpx async HTTP calls."""

    def test_exception_injection_on_llm_call(self, agent, echo_server):
        """Inject ConnectError into httpx calls to a specific host."""
        # 1. Normal call should succeed
        async def make_llm_call():
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{echo_server}/compatible-mode/v1/chat/completions",
                    json={"model": "qwen-plus", "messages": [{"role": "user", "content": "hello"}]},
                    headers={"Authorization": "Bearer test-key"},
                )
                return resp

        resp = asyncio.run(make_llm_call())
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Hello! I am a test LLM response."

        # 2. Create exception injection experiment targeting the echo server host
        suid = "httpx-exc-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "host": "127.0.0.1",
            "exception": "ConnectError",
            "exception-message": "LLM service unavailable - chaos injection",
        })
        assert result["code"] == 200, f"Create failed: {result}"

        # 3. Call should now raise ConnectError
        try:
            with pytest.raises(Exception) as exc_info:
                asyncio.run(make_llm_call())
            assert "LLM service unavailable - chaos injection" in str(exc_info.value)
        finally:
            # 4. Destroy experiment
            destroy_result = _api_destroy(agent, suid)
            assert destroy_result["code"] == 200

        # 5. Call should work again after destroy
        resp = asyncio.run(make_llm_call())
        assert resp.status_code == 200

    def test_exception_injection_with_url_matcher(self, agent, echo_server):
        """Inject exception only for specific URL path (chat/completions)."""
        suid = "httpx-exc-002"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "path": "/compatible-mode/v1/chat/completions",
            "exception": "TimeoutException",
            "exception-message": "DashScope API timeout - chaos injection",
        })
        assert result["code"] == 200

        try:
            # LLM completion endpoint should fail
            async def call_completions():
                async with httpx.AsyncClient() as client:
                    return await client.post(
                        f"{echo_server}/compatible-mode/v1/chat/completions",
                        json={"model": "qwen-plus", "messages": []},
                    )

            with pytest.raises(Exception) as exc_info:
                asyncio.run(call_completions())
            assert "DashScope API timeout" in str(exc_info.value)

            # Other endpoints should still work
            async def call_health():
                async with httpx.AsyncClient() as client:
                    return await client.get(f"{echo_server}/health")

            resp = asyncio.run(call_health())
            assert resp.status_code == 200
        finally:
            _api_destroy(agent, suid)


# ---------------------------------------------------------------------------
# Test: httpx delay injection (simulating LLM latency)
# ---------------------------------------------------------------------------


class TestHttpxDelayInjection:
    """Verify delay injection on httpx async HTTP calls."""

    def test_delay_injection_on_llm_call(self, agent, echo_server):
        """Inject 500ms delay into httpx calls."""
        # Baseline timing
        async def timed_call():
            async with httpx.AsyncClient() as client:
                start = time.time()
                resp = await client.post(
                    f"{echo_server}/compatible-mode/v1/chat/completions",
                    json={"model": "qwen-plus", "messages": [{"role": "user", "content": "hi"}]},
                )
                elapsed = time.time() - start
                return resp, elapsed

        resp, baseline = asyncio.run(timed_call())
        assert resp.status_code == 200
        assert baseline < 1.0  # Should be fast (local echo server)

        # Create delay experiment
        suid = "httpx-delay-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "delay",
            "host": "127.0.0.1",
            "time": "500",
        })
        assert result["code"] == 200

        try:
            # Call should now be delayed by ~500ms
            resp, elapsed = asyncio.run(timed_call())
            assert resp.status_code == 200
            assert elapsed >= 0.4, f"Expected delay >=400ms, got {elapsed*1000:.0f}ms"
        finally:
            _api_destroy(agent, suid)

        # After destroy, should be fast again
        resp, elapsed = asyncio.run(timed_call())
        assert resp.status_code == 200
        assert elapsed < 1.0


# ---------------------------------------------------------------------------
# Test: httpx returnValue injection (simulating modified LLM response)
# ---------------------------------------------------------------------------


class TestHttpxReturnValueInjection:
    """Verify return value injection on httpx async calls."""

    def test_return_value_injection(self, agent, echo_server):
        """Inject custom return value for httpx calls."""
        suid = "httpx-ret-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "returnValue",
            "host": "127.0.0.1",
            "return-value": "injected_response",
        })
        assert result["code"] == 200

        try:
            async def make_call():
                async with httpx.AsyncClient() as client:
                    return await client.post(
                        f"{echo_server}/compatible-mode/v1/chat/completions",
                        json={"model": "qwen-plus", "messages": []},
                    )

            # The return value should be the injected string
            ret = asyncio.run(make_call())
            assert ret == "injected_response"
        finally:
            _api_destroy(agent, suid)


# ---------------------------------------------------------------------------
# Test: experiment lifecycle (create → status → destroy → verify recovery)
# ---------------------------------------------------------------------------


class TestHttpxExperimentLifecycle:
    """Verify full experiment lifecycle."""

    def test_create_status_destroy_cycle(self, agent, echo_server):
        """Full lifecycle: create → query status → hit → destroy → recover."""
        # Create
        suid = "httpx-lifecycle-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "host": "127.0.0.1",
            "exception": "ConnectError",
            "exception-message": "lifecycle test error",
        })
        assert result["code"] == 200

        # Status should show active
        status = _api_status(agent, suid)
        assert status["code"] == 200

        # Hit the injection
        async def trigger():
            async with httpx.AsyncClient() as client:
                return await client.get(f"{echo_server}/test")

        with pytest.raises(Exception) as exc_info:
            asyncio.run(trigger())
        assert "lifecycle test error" in str(exc_info.value)

        # Destroy
        destroy_result = _api_destroy(agent, suid)
        assert destroy_result["code"] == 200

        # Recovery - should work again
        resp = asyncio.run(trigger())
        assert resp.status_code == 200

    def test_effect_count_limiting(self, agent, echo_server):
        """effect-count=2 should only inject the first 2 calls."""
        suid = "httpx-count-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "host": "127.0.0.1",
            "exception": "ConnectError",
            "exception-message": "limited injection",
            "effect-count": "2",
        })
        assert result["code"] == 200

        try:
            async def call():
                async with httpx.AsyncClient() as client:
                    return await client.get(f"{echo_server}/test")

            # First 2 calls should fail
            for i in range(2):
                with pytest.raises(Exception) as exc_info:
                    asyncio.run(call())
                assert "limited injection" in str(exc_info.value), f"Call {i+1} should fail"

            # 3rd call should succeed (effect-count exhausted)
            resp = asyncio.run(call())
            assert resp.status_code == 200, "3rd call should succeed after effect-count exhausted"
        finally:
            _api_destroy(agent, suid)


# ---------------------------------------------------------------------------
# Test: method matcher (POST-only injection, GET unaffected)
# ---------------------------------------------------------------------------


class TestHttpxMethodMatcher:
    """Verify method-based matcher works."""

    def test_post_only_injection(self, agent, echo_server):
        """Inject exception only on POST requests, GET should pass through."""
        suid = "httpx-method-001"
        result = _api_create(agent, {
            "suid": suid,
            "target": "httpx",
            "action": "throwCustomException",
            "host": "127.0.0.1",
            "method": "POST",
            "exception": "ConnectError",
            "exception-message": "POST only fault",
        })
        assert result["code"] == 200

        try:
            # POST should fail
            async def post_call():
                async with httpx.AsyncClient() as client:
                    return await client.post(f"{echo_server}/api/chat", json={})

            with pytest.raises(Exception) as exc_info:
                asyncio.run(post_call())
            assert "POST only fault" in str(exc_info.value)

            # GET should still work
            async def get_call():
                async with httpx.AsyncClient() as client:
                    return await client.get(f"{echo_server}/health")

            resp = asyncio.run(get_call())
            assert resp.status_code == 200
        finally:
            _api_destroy(agent, suid)
