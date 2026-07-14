"""gRPC plugin - fault injection for grpc-python (grpcio).

Intercepts grpc._channel._UnaryUnaryMultiCallable.__call__ to inject:
- delay: latency on unary-unary RPC calls
- exception: RpcError / StatusCode errors
- return: tampered responses

Matchers:
- method: gRPC method path (e.g., "/package.Service/Method")
- service: gRPC service name
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


def _grpc_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract gRPC-specific matchers.

    _UnaryUnaryMultiCallable.__call__(self, request, timeout=None, metadata=None, ...)
    The '_method' attribute on the callable object contains the full method path.
    - obj = the _UnaryUnaryMultiCallable instance
    """
    matchers: dict[str, str] = {}

    # obj is the stub callable, which has a _method attribute
    if obj is not None:
        method_path = getattr(obj, "_method", None)
        if method_path:
            # _method is bytes in grpcio, decode to str
            if isinstance(method_path, bytes):
                method_path = method_path.decode("utf-8", errors="replace")
            matchers["method"] = method_path

            # Extract service name: "/package.Service/Method" -> "package.Service"
            parts = method_path.strip("/").rsplit("/", 1)
            if len(parts) >= 1:
                matchers["service"] = parts[0]

    return matchers


class GrpcModelSpec(BaseModelSpec):
    """ModelSpec for gRPC fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "grpc"

    def get_short_desc(self) -> str:
        return "gRPC fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into gRPC calls"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("method", "gRPC method path (e.g., /pkg.Svc/Method)"),
            DefaultMatcherSpec("service", "gRPC service name"),
        ]

    def _register_actions(self) -> None:
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into gRPC calls",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from gRPC calls",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override gRPC response",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class GrpcPlugin:
    """gRPC fault injection plugin.

    Target: grpc._channel._UnaryUnaryMultiCallable.__call__
    """

    def __init__(self) -> None:
        self._model_spec = GrpcModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="grpc._channel",
            target_function="__call__",
            target_class="_UnaryUnaryMultiCallable",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="grpc",
            extractor=_grpc_matcher_extractor,
        )

    def get_name(self) -> str:
        return "grpc"

    def get_model_spec(self) -> GrpcModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
