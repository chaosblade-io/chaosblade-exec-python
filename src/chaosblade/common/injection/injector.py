"""Injector - core injection engine that matches experiments and executes actions.

This is the heart of ChaosBlade: for each method interception, it compares
active experiments against the runtime EnhancerModel and triggers fault injection.

Ported from Java: chaosblade-exec-common/.../injection/Injector.java
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.center.status_manager import StatusMetric
    from chaosblade.common.model.enhancer_model import EnhancerModel
    from chaosblade.common.model.model import Model

from chaosblade.common.center.manager_factory import ManagerFactory
from chaosblade.common.exception.interrupt_process import InterruptProcessException

logger = logging.getLogger(__name__)

# Matcher key constants
EFFECT_COUNT_MATCHER_NAME = "effect-count"
EFFECT_PERCENT_MATCHER_NAME = "effect-percent"
REGEX_PATTERN_FLAG = "-regex"

# Safety constants
_MAX_INJECTION_TIME_MS = 30000  # 30s max for any single injection
_MAX_COMPARE_ITERATIONS = 1000  # Safety cap on experiment rules per target


class Injector:
    """Core injection engine.

    Flow: get active experiments for target -> compare -> limitAndIncrease -> merge -> execute
    Only matches the FIRST matching rule (break after match).
    """

    # Global switch - when False, all injection is bypassed
    _enabled: bool = True
    _lock = threading.Lock()

    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        """Global switch to enable/disable all injection."""
        cls._enabled = enabled
        logger.info("Injector %s", "enabled" if enabled else "disabled")

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if injector is enabled."""
        return cls._enabled

    @staticmethod
    def inject(enhancer_model: EnhancerModel) -> None:
        """Main injection entry point.

        Args:
            enhancer_model: Runtime model built by the Enhancer with actual values.

        Raises:
            InterruptProcessException: When injection succeeds and the target
                method should be interrupted.
        """
        # Safety: global switch check
        if not Injector._enabled:
            return

        target = enhancer_model.target
        status_metrics = ManagerFactory.get_status_manager().get_exp_by_target(target)

        iteration = 0
        for status_metric in status_metrics:
            iteration += 1
            if iteration > _MAX_COMPARE_ITERATIONS:
                logger.warning(
                    "Safety cap reached: too many rules for target '%s'", target
                )
                break
            model = status_metric.model
            if not Injector._compare(model, enhancer_model):
                continue

            try:
                if not Injector._limit_and_increase(status_metric):
                    logger.debug("Limited, skip injection: %s", model)
                    break

                logger.debug("Match rule: %s", model)
                enhancer_model.merge(model)

                model_spec = ManagerFactory.get_model_spec_manager().get_model_spec(target)
                if model_spec is None:
                    logger.warning("ModelSpec not found for target: %s", target)
                    break

                action_spec = model_spec.get_action_spec(model.action_name)
                if action_spec is None:
                    logger.warning("ActionSpec not found: %s", model.action_name)
                    break

                action_spec.get_action_executor().run(enhancer_model)
            except InterruptProcessException:
                raise
            except Exception:
                logger.warning("Injection execution error, rolling back count", exc_info=True)
                status_metric.decrease()

            # Only match the first rule (Java: break after first match)
            break

    @staticmethod
    def _limit_and_increase(status_metric: StatusMetric) -> bool:
        """Check effect-count/effect-percent limits and increment counter.

        Returns:
            True if injection should proceed, False if limited.
        """
        model = status_metric.model

        # Check effect-count limit
        limit_count_str = model.matcher.get(EFFECT_COUNT_MATCHER_NAME)
        if limit_count_str is not None and str(limit_count_str).strip():
            count = int(limit_count_str)
            return status_metric.increase_with_lock(count)

        # Check effect-percent limit
        limit_percent_str = model.matcher.get(EFFECT_PERCENT_MATCHER_NAME)
        if limit_percent_str is not None and str(limit_percent_str).strip():
            percent = int(limit_percent_str)
            random_value = random.randint(1, 100)
            if random_value > percent:
                return False

        status_metric.increase()
        return True

    @staticmethod
    def _compare(model: Model, enhancer_model: EnhancerModel) -> bool:
        """Compare experiment model matchers against runtime enhancer model values.

        Rules:
        - If model has no matchers (None/empty): return True (match all)
        - Skip effect-count and effect-percent matchers
        - For each matcher key: check exact match (case-insensitive), then regex
        - CustomMatcher takes priority if registered for a key
        """
        matcher = model.matcher
        matchers = matcher.matchers

        # None or empty matchers -> match all
        if not matchers:
            return True

        enhancer_matcher_model = enhancer_model.matcher_model
        if enhancer_matcher_model is None:
            return False

        for key, rule_value in matchers.items():
            # Skip control matchers
            if key in (EFFECT_COUNT_MATCHER_NAME, EFFECT_PERCENT_MATCHER_NAME):
                continue

            actual_value = enhancer_matcher_model.get(key)
            if actual_value is None:
                return False

            rule_str = str(rule_value)
            actual_str = str(actual_value)

            # Check for custom matcher
            custom_matcher = enhancer_model.get_matcher(key)
            if custom_matcher is None:
                # Default matching: case-insensitive exact match
                if actual_str.lower() == rule_str.lower():
                    continue
                # Regex suffix matching
                if key.endswith(REGEX_PATTERN_FLAG):
                    try:
                        if re.fullmatch(rule_str, actual_str):
                            continue
                    except re.error:
                        pass
                return False
            else:
                # Custom matcher
                if key.endswith(REGEX_PATTERN_FLAG):
                    if custom_matcher.regex_match(rule_str, actual_value):
                        continue
                else:
                    if custom_matcher.match(rule_str, actual_value):
                        continue
                return False

        return True
