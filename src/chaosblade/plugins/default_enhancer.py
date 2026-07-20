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
