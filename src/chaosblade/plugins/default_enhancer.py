"""Default BeforeEnhancer implementation for plugins.

Provides a generic enhancer that extracts matchers from method arguments
using a configurable strategy.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from chaosblade.common.model.enhancer_model import EnhancerModel
from chaosblade.common.model.matcher_model import MatcherModel
from chaosblade.spi.enhancer import BeforeEnhancer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Type alias for a matcher extractor function
# Receives (method_name, obj, args, kwargs) and returns dict of matcher_key -> value
MatcherExtractor = Callable[[str, Any, tuple, dict], dict[str, str]]


class DefaultBeforeEnhancer(BeforeEnhancer):
    """Generic before-enhancer that uses a MatcherExtractor to populate matchers.

    Each plugin provides its own extractor function that knows how to
    extract matcher values from the target method's arguments.
    """

    def __init__(self, target: str, extractor: MatcherExtractor | None = None) -> None:
        self._target = target
        self._extractor = extractor

    def get_target(self) -> str:
        return self._target

    def do_before_advice(
        self,
        target: str,
        method_name: str,
        obj: Any,
        args: tuple,
        kwargs: dict,
    ) -> EnhancerModel | None:
        """Build EnhancerModel with matchers extracted from args."""
        matcher_model = MatcherModel()

        # Always add method name as a matcher
        matcher_model.add("method", method_name)

        # Use extractor to get additional matchers
        if self._extractor is not None:
            try:
                extracted = self._extractor(method_name, obj, args, kwargs)
                for k, v in extracted.items():
                    matcher_model.add(k, v)
            except Exception:
                logger.debug(
                    "Matcher extraction failed for %s.%s", target, method_name,
                    exc_info=True,
                )

        return EnhancerModel(matcher_model)
