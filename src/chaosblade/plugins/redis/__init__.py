"""Redis plugin - fault injection for redis-py client.

Intercepts redis.client.Redis.execute_command to inject:
- delay: latency on Redis operations
- exception: ConnectionError / TimeoutError
- return: tampered return values

Matchers:
- cmd: Redis command name (GET, SET, HGET, etc.)
- key: Redis key (first argument)
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


def _redis_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract Redis-specific matchers from execute_command args.

    redis.client.Redis.execute_command(self, *args, **options)
    - args[0] is 'self' (the Redis instance) in the wrapper context
    - args[1] is the command name (e.g., "GET")
    - args[2] is typically the key
    """
    matchers: dict[str, str] = {}

    # args[0] = self (Redis instance), args[1] = command, args[2] = key
    if len(args) >= 2:
        matchers["cmd"] = str(args[1]).upper()
    if len(args) >= 3:
        matchers["key"] = str(args[2])

    return matchers


class RedisModelSpec(BaseModelSpec):
    """ModelSpec for Redis fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "redis"

    def get_short_desc(self) -> str:
        return "Redis fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into Redis operations"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("cmd", "Redis command to match (e.g., GET, SET)"),
            DefaultMatcherSpec("key", "Redis key pattern to match"),
        ]

    def _register_actions(self) -> None:
        """Register delay/exception/return actions."""
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into Redis operations",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from Redis operations",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override Redis operation return value",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class RedisPlugin:
    """Redis fault injection plugin.

    Target: redis.client.Redis.execute_command
    """

    def __init__(self) -> None:
        self._model_spec = RedisModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="redis.client",
            target_function="execute_command",
            target_class="Redis",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="redis",
            extractor=_redis_matcher_extractor,
        )

    def get_name(self) -> str:
        return "redis"

    def get_model_spec(self) -> RedisModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
