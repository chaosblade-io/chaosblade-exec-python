"""MySQL plugin - fault injection for mysql-connector-python and PyMySQL.

Intercepts cursor.execute to inject:
- delay: latency on SQL queries
- exception: OperationalError / InterfaceError
- return: tampered query results

Matchers:
- sql: SQL statement text
- database: target database name
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


def _mysql_matcher_extractor(
    method_name: str, obj: Any, args: tuple, kwargs: dict
) -> dict[str, str]:
    """Extract MySQL-specific matchers from cursor.execute args.

    cursor.execute(self, operation, params=None, multi=False)
    - args[0] = self (cursor instance)
    - args[1] = SQL operation string
    """
    matchers: dict[str, str] = {}

    # args[0] = self (cursor), args[1] = SQL string
    if len(args) >= 2:
        sql = str(args[1]).strip()
        matchers["sql"] = sql

        # Extract SQL type (SELECT, INSERT, UPDATE, DELETE, etc.)
        first_word = sql.split(None, 1)[0].upper() if sql else ""
        if first_word:
            matchers["sqltype"] = first_word

    # Try to get database name from connection
    if len(args) >= 1 and obj is not None:
        # Try common cursor → connection → database patterns
        connection = getattr(obj, "connection", None) or getattr(obj, "_connection", None)
        if connection:
            db = (
                getattr(connection, "database", None)
                or getattr(connection, "db", None)
                or getattr(connection, "_database", None)
            )
            if db:
                matchers["database"] = str(db)

    return matchers


class MysqlModelSpec(BaseModelSpec):
    """ModelSpec for MySQL fault injection."""

    def __init__(self) -> None:
        super().__init__()
        self._register_actions()

    def get_target(self) -> str:
        return "mysql"

    def get_short_desc(self) -> str:
        return "MySQL fault injection"

    def get_long_desc(self) -> str:
        return "Inject delay, exception, or return value faults into MySQL operations"

    def get_matcher_specs(self) -> list[DefaultMatcherSpec]:
        return [
            DefaultMatcherSpec("sql", "SQL statement pattern to match"),
            DefaultMatcherSpec("sqltype", "SQL type to match (SELECT, INSERT, etc.)"),
            DefaultMatcherSpec("database", "Database name to match"),
        ]

    def _register_actions(self) -> None:
        """Register delay/exception/return actions."""
        self.add_action_spec(DefaultActionSpec(
            name="delay",
            short_desc="Inject latency into MySQL operations",
            flags=[
                DefaultFlagSpec("time", "Delay duration in milliseconds", _required=True),
                DefaultFlagSpec("offset", "Random offset range in milliseconds"),
            ],
            executor=DelayActionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="throwCustomException",
            short_desc="Throw exception from MySQL operations",
            aliases=["exception"],
            flags=[
                DefaultFlagSpec("exception", "Exception class name"),
                DefaultFlagSpec("exception-message", "Exception message"),
            ],
            executor=ThrowExceptionExecutor(),
        ))

        self.add_action_spec(DefaultActionSpec(
            name="returnValue",
            short_desc="Override MySQL query result",
            aliases=["return"],
            flags=[
                DefaultFlagSpec("return-value", "Value to return"),
            ],
            executor=ReturnValueExecutor(),
        ))


class MysqlPlugin:
    """MySQL fault injection plugin.

    Target: mysql.connector.cursor.MySQLCursor.execute
    Also works with PyMySQL's cursor.execute via similar structure.
    """

    def __init__(self) -> None:
        self._model_spec = MysqlModelSpec()
        # Default to mysql-connector-python; can also add PyMySQL variant
        self._point_cut = DefaultPointCut(
            target_module="mysql.connector.cursor",
            target_function="execute",
            target_class="MySQLCursor",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="mysql",
            extractor=_mysql_matcher_extractor,
        )

    def get_name(self) -> str:
        return "mysql"

    def get_model_spec(self) -> MysqlModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer


class PyMysqlPlugin:
    """PyMySQL fault injection plugin variant.

    Target: pymysql.cursors.Cursor.execute
    """

    def __init__(self) -> None:
        self._model_spec = MysqlModelSpec()
        self._point_cut = DefaultPointCut(
            target_module="pymysql.cursors",
            target_function="execute",
            target_class="Cursor",
        )
        self._enhancer = DefaultBeforeEnhancer(
            target="mysql",
            extractor=_mysql_matcher_extractor,
        )

    def get_name(self) -> str:
        return "pymysql"

    def get_model_spec(self) -> MysqlModelSpec:
        return self._model_spec

    def get_point_cut(self) -> DefaultPointCut:
        return self._point_cut

    def get_enhancer(self) -> DefaultBeforeEnhancer:
        return self._enhancer
