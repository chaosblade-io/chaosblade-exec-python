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

"""SQLAlchemy plugin - fault injection at the ORM/engine layer.

Intercepts sqlalchemy.engine.Engine.execute (or Connection.execute) to inject:
- delay: latency on SQL execution
- exception: OperationalError / DatabaseError
- return: tampered results

Matchers:
- sql: SQL statement text
- sqltype: SQL type (SELECT, INSERT, etc.)
- database: database URL scheme
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


def _sqlalchemy_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract SQLAlchemy-specific matchers.

    Connection.execute(self, statement, parameters=None, ...)
    - args[0] = self (Connection instance)
    - args[1] = statement (str or ClauseElement)
    """
    matchers: dict[str, str] = {}

    # args[0] = self (Connection), args[1] = statement
    if len(args) >= 2:
        statement = args[1]
        sql_str = str(statement).strip()
        matchers["sql"] = sql_str

        # Extract SQL type
        first_word = sql_str.split(None, 1)[0].upper() if sql_str else ""
        if first_word:
            matchers["sqltype"] = first_word

    # Try to get database URL from the engine
    if obj is not None:
        engine = getattr(obj, "engine", None) or getattr(obj, "_engine", None)
        if engine:
            url = getattr(engine, "url", None)
            if url:
                # Get the driver/scheme part (e.g., "postgresql", "mysql")
                backend = getattr(url, "drivername", None) or str(url).split("://")[0]
                if backend:
                    matchers["database"] = str(backend)

    return matchers


class SqlalchemyModelSpec(BaseModelSpec):
    """ModelSpec for SQLAlchemy fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "sqlalchemy"

    def get_short_desc(self) -> str:
        return "SQLAlchemy fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into SQLAlchemy operations"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("sql", "SQL statement pattern to match"),
            DefaultMatcherSpec("sqltype", "SQL type to match (SELECT, INSERT, etc.)"),
            DefaultMatcherSpec("database", "Database driver/scheme to match"),
        ]

    def _register_actions(self) -> None:
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into SQLAlchemy operations",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from SQLAlchemy operations",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override SQLAlchemy query result",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class SqlalchemyPlugin:
    """SQLAlchemy fault injection plugin.

    Target: sqlalchemy.engine.Connection.execute
    """

    def __init__(self) -> None:
        self._model_spec = SqlalchemyModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="sqlalchemy.engine.base",
            target_function="execute",
            target_class="Connection",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="sqlalchemy",
            extractor=_sqlalchemy_matcher_extractor,
        )

    def get_name(self) -> str:
        return "sqlalchemy"

    def get_model_spec(self) -> SqlalchemyModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
