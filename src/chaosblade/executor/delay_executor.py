"""DelayActionExecutor - injects latency into method calls.

Equivalent to Java's DefaultDelayExecutor.
Flags:
  - time: delay duration in milliseconds (required)
  - offset: random offset range in milliseconds (optional, default 0)
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel

from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
)

logger = logging.getLogger(__name__)

# Flag names matching ChaosBlade conventions
FLAG_TIME = "time"
FLAG_OFFSET = "offset"


class DelayActionExecutor:
    """Executor that injects latency (sleep) before the target method executes.

    After sleeping, raises InterruptProcessException with RETURN_IMMEDIATELY
    if the target was already called, or just returns to let the original continue.

    The `time` flag specifies base delay in ms.
    The `offset` flag specifies random jitter (0 to offset ms added).
    """

    def run(self, enhancer_model: EnhancerModel) -> None:
        """Execute the delay injection.

        Reads 'time' and 'offset' from action flags, sleeps, then lets
        the original method proceed normally (no interrupt - caller handles).
        """
        time_ms = self._get_delay_ms(enhancer_model)
        offset_ms = self._get_offset_ms(enhancer_model)

        # Calculate actual delay with optional jitter
        if offset_ms > 0:
            actual_ms = time_ms + random.randint(0, offset_ms)
        else:
            actual_ms = time_ms

        if actual_ms <= 0:
            return

        logger.debug("Injecting delay: %d ms (base=%d, offset=%d)", actual_ms, time_ms, offset_ms)

        # Sleep for the specified duration
        time.sleep(actual_ms / 1000.0)

        # After delay, we do NOT interrupt - let the original method proceed
        # The delay itself is the fault injection effect

    def _get_delay_ms(self, enhancer_model: EnhancerModel) -> int:
        """Get the delay time in milliseconds from action flags."""
        value = enhancer_model.get_action_flag(FLAG_TIME)
        if value is None:
            logger.warning("Delay executor missing 'time' flag, defaulting to 0")
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning("Invalid delay time value: %s", value)
            return 0

    def _get_offset_ms(self, enhancer_model: EnhancerModel) -> int:
        """Get the offset (jitter) in milliseconds from action flags."""
        value = enhancer_model.get_action_flag(FLAG_OFFSET)
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
