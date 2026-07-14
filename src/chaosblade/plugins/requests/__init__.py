"""Requests (HTTP Client) plugin - fault injection for the requests library.

Intercepts requests.adapters.HTTPAdapter.send to inject:
- delay: latency on HTTP requests
- exception: ConnectionError / Timeout / HTTPError
- return: tampered responses

Matchers:
- url: request URL
- method: HTTP method (GET, POST, etc.)
- host: target hostname
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


def _requests_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract HTTP request matchers from HTTPAdapter.send args.

    HTTPAdapter.send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None)
    - args[0] = self (HTTPAdapter instance)
    - args[1] = PreparedRequest object
    """
    matchers: dict[str, str] = {}

    # args[0] = self, args[1] = PreparedRequest
    if len(args) >= 2:
        request = args[1]
        url = getattr(request, "url", None)
        http_method = getattr(request, "method", None)

        if url:
            matchers["url"] = str(url)
            # Extract host from URL
            try:
                from urllib.parse import urlparse
                parsed = urlparse(str(url))
                if parsed.hostname:
                    matchers["host"] = parsed.hostname
            except Exception:
                pass

        if http_method:
            matchers["method"] = str(http_method).upper()

    return matchers


class RequestsModelSpec(BaseModelSpec):
    """ModelSpec for requests (HTTP client) fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "http"

    def get_short_desc(self) -> str:
        return "HTTP client (requests) fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into HTTP requests"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("url", "Request URL pattern to match"),
            DefaultMatcherSpec("method", "HTTP method to match (GET, POST, etc.)"),
            DefaultMatcherSpec("host", "Target hostname to match"),
        ]

    def _register_actions(self) -> None:
        """Register delay/exception/return actions."""
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into HTTP requests",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from HTTP requests",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name (e.g., ConnectionError)"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override HTTP response",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class RequestsPlugin:
    """HTTP client (requests) fault injection plugin.

    Target: requests.adapters.HTTPAdapter.send
    """

    def __init__(self) -> None:
        self._model_spec = RequestsModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="requests.adapters",
            target_function="send",
            target_class="HTTPAdapter",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="http",
            extractor=_requests_matcher_extractor,
        )

    def get_name(self) -> str:
        return "http"

    def get_model_spec(self) -> RequestsModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
