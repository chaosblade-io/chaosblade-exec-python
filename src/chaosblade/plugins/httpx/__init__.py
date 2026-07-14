"""HTTPX plugin - fault injection for the httpx async/sync HTTP client library.

Intercepts httpx._client.AsyncClient.send to inject:
- delay: latency on HTTP requests
- exception: ConnectError / TimeoutException / HTTPStatusError
- return: tampered responses

Matchers:
- url: full request URL
- method: HTTP method (GET, POST, etc.)
- host: target hostname
- path: URL path
"""

from __future__ import annotations

from typing import Any

from chaosblade.common.model.base_model_spec import BaseModelSpec
from chaosblade.executor.delay_executor import DelayActionExecutor
from chaosblade.executor.exception_executor import ThrowExceptionExecutor
from chaosblade.executor.return_executor import ReturnValueExecutor
from chaosblade.plugins.base import (
    DefaultActionSpec,
    DefaultFlagSpec,
    DefaultMatcherSpec,
    DefaultPointCut,
)
from chaosblade.plugins.default_enhancer import DefaultBeforeEnhancer


def _httpx_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract HTTP request matchers from httpx AsyncClient.send / Client.send args.

    AsyncClient.send(self, request, *, stream=False, auth=..., follow_redirects=...)
    - args[0] = self (AsyncClient/Client instance)
    - args[1] = httpx.Request object
    """
    matchers: dict[str, str] = {}

    # args[0] = self, args[1] = httpx.Request
    if len(args) >= 2:
        request = args[1]
        url = getattr(request, "url", None)
        http_method = getattr(request, "method", None)

        if url:
            matchers["url"] = str(url)
            # Extract host and path from URL
            host = getattr(url, "host", None)
            path = getattr(url, "path", None) or getattr(url, "raw_path", None)
            if host:
                matchers["host"] = str(host)
            if path:
                matchers["path"] = str(path)

        if http_method:
            matchers["method"] = str(http_method).upper()

    return matchers


class HttpxModelSpec(BaseModelSpec):
    """ModelSpec for httpx (async HTTP client) fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "httpx"

    def get_short_desc(self) -> str:
        return "HTTPX async/sync HTTP client fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into httpx HTTP requests"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("url", "Full request URL to match"),
            DefaultMatcherSpec("method", "HTTP method to match (GET, POST, etc.)"),
            DefaultMatcherSpec("host", "Target hostname to match"),
            DefaultMatcherSpec("path", "URL path to match"),
        ]

    def _register_actions(self) -> None:
        """Register delay/exception/return actions."""
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into httpx requests",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from httpx requests",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name (e.g., ConnectError, TimeoutException)"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override httpx response",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class HttpxPlugin:
    """HTTPX async HTTP client fault injection plugin.

    Target: httpx._client.AsyncClient.send
    This intercepts all async HTTP requests made via httpx, including those
    from langchain-openai (ChatOpenAI) and the openai SDK.
    """

    def __init__(self) -> None:
        self._model_spec = HttpxModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="httpx._client",
            target_function="send",
            target_class="AsyncClient",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="httpx",
            extractor=_httpx_matcher_extractor,
        )

    def get_name(self) -> str:
        return "httpx"

    def get_model_spec(self) -> HttpxModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
