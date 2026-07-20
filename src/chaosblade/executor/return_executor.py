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

"""ReturnValueExecutor - tampers with method return values.

Equivalent to Java's DefaultReturnValueExecutor.
Flags:
  - return-value: the value to return (as string, will be parsed)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel

from chaosblade.common.exception.interrupt_process import throw_return_immediately

logger = logging.getLogger(__name__)

# Flag name
FLAG_RETURN_VALUE = "return-value"


class ReturnValueExecutor:
    """Executor that overrides the return value of the target method.

    The return value is specified as a string flag and parsed:
    - "null" / "none" / "None" → None
    - "true" / "True" → True
    - "false" / "False" → False
    - Integer string → int
    - Float string → float
    - JSON string (starts with { or [) → parsed JSON
    - Otherwise → raw string value
    """

    def run(self, enhancer_model: EnhancerModel) -> None:
        """Execute the return value injection.

        Reads 'return-value' from action flags, parses it,
        and raises InterruptProcessException with RETURN_IMMEDIATELY.
        """
        raw_value = enhancer_model.get_action_flag(FLAG_RETURN_VALUE)

        if raw_value is None:
            # No return value specified - return None
            logger.debug("No return-value flag, returning None")
            throw_return_immediately(None)
            return  # unreachable but for clarity

        parsed = self._parse_value(raw_value)

        logger.debug("Injecting return value: %r (raw=%r)", parsed, raw_value)
        throw_return_immediately(parsed)

    def _parse_value(self, raw: str) -> object:
        """Parse the raw string value into an appropriate Python type.

        Args:
            raw: The raw string value from the flag.

        Returns:
            The parsed value.
        """
        # Handle null/none
        if raw.lower() in ("null", "none"):
            return None

        # Handle booleans
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False

        # Handle integers
        try:
            return int(raw)
        except ValueError:
            pass

        # Handle floats
        try:
            return float(raw)
        except ValueError:
            pass

        # Handle JSON objects/arrays
        if raw.startswith(("{", "[")):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                pass

        # Return as raw string
        return raw
