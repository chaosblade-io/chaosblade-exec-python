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

"""EnhancerFactory - creates before/after wrappers that bridge MonkeyPatcher to Enhancer.

This factory creates the wrapper function that MonkeyPatcher installs. The wrapper
invokes the BeforeEnhancer (which triggers Injector) and handles InterruptProcessException.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.spi.enhancer import BeforeEnhancer, AfterEnhancer
    from chaosblade.spi.point_cut import PointCut

from chaosblade.common.exception.interrupt_process import (
    InterruptProcessException,
    ProcessState,
)

logger = logging.getLogger(__name__)


class EnhancerFactory:
    """Creates wrapper functions that bridge monkey patching to the Enhancer/Injector system.

    The created wrapper:
    1. Calls BeforeEnhancer.before_advice() to build EnhancerModel and trigger Injector
    2. If InterruptProcessException is raised:
       - RETURN_IMMEDIATELY: return the response value
       - THROWS_IMMEDIATELY: raise the wrapped exception
    3. Otherwise: call the original function normally
    4. Optionally calls AfterEnhancer.after_advice() on the return value
    """

    @staticmethod
    def create_before_wrapper(
        target: str,
        before_enhancer: BeforeEnhancer,
        after_enhancer: AfterEnhancer | None = None,
    ) -> Callable:
        """Create a wrapper function for use with MonkeyPatcher.

        Args:
            target: The experiment target name (e.g., "redis")
            before_enhancer: The before-advice enhancer instance
            after_enhancer: Optional after-advice enhancer instance

        Returns:
            A wrapper function with signature: wrapper(original, *args, **kwargs)
        """

        def wrapper(original: Callable, *args: Any, **kwargs: Any) -> Any:
            # Determine the method name from the original function
            method_name = getattr(original, "__name__", "unknown")

            # Determine 'self/obj' - first positional arg if it's a method
            obj = args[0] if args else None

            try:
                before_enhancer.before_advice(
                    target, method_name, obj, args, kwargs
                )
            except InterruptProcessException as e:
                if e.state == ProcessState.RETURN_IMMEDIATELY:
                    return e.response
                elif e.state == ProcessState.THROWS_IMMEDIATELY:
                    if e.exception is not None:
                        raise e.exception
                    raise
            except Exception:
                # Enhancer errors should not break the target application
                logger.warning(
                    "Error in before_advice for target=%s, method=%s",
                    target,
                    method_name,
                    exc_info=True,
                )

            # Call original
            result = original(*args, **kwargs)

            # After advice (if provided)
            if after_enhancer is not None:
                try:
                    after_enhancer.after_advice(target, method_name, obj, result)
                except Exception:
                    logger.warning(
                        "Error in after_advice for target=%s", target, exc_info=True
                    )

            return result

        return wrapper

    @staticmethod
    def create_async_before_wrapper(
        target: str,
        before_enhancer: BeforeEnhancer,
        after_enhancer: AfterEnhancer | None = None,
    ) -> Callable:
        """Create an async wrapper function for use with MonkeyPatcher.

        Same logic as create_before_wrapper but handles coroutine functions.
        """

        async def async_wrapper(original: Callable, *args: Any, **kwargs: Any) -> Any:
            method_name = getattr(original, "__name__", "unknown")
            obj = args[0] if args else None

            try:
                before_enhancer.before_advice(
                    target, method_name, obj, args, kwargs
                )
            except InterruptProcessException as e:
                if e.state == ProcessState.RETURN_IMMEDIATELY:
                    return e.response
                elif e.state == ProcessState.THROWS_IMMEDIATELY:
                    if e.exception is not None:
                        raise e.exception
                    raise
            except Exception:
                logger.warning(
                    "Error in before_advice for target=%s, method=%s",
                    target,
                    method_name,
                    exc_info=True,
                )

            # Call original (awaiting the coroutine)
            result = await original(*args, **kwargs)

            if after_enhancer is not None:
                try:
                    after_enhancer.after_advice(target, method_name, obj, result)
                except Exception:
                    logger.warning(
                        "Error in after_advice for target=%s", target, exc_info=True
                    )

            return result

        return async_wrapper

    @staticmethod
    def create_wrapper_for_point_cut(
        target: str,
        point_cut: Any,
        before_enhancer: BeforeEnhancer,
        after_enhancer: AfterEnhancer | None = None,
    ) -> Callable:
        """Create the appropriate wrapper (sync or async) based on the target function.

        Inspects the actual target to determine if it's async.
        Falls back to sync wrapper if target is not yet imported.
        """
        import sys

        module = sys.modules.get(point_cut.get_target_module())
        if module is not None:
            target_class = point_cut.get_target_class()
            if target_class:
                cls = getattr(module, target_class, None)
                func = getattr(cls, point_cut.get_target_function(), None) if cls else None
            else:
                func = getattr(module, point_cut.get_target_function(), None)

            if func is not None and inspect.iscoroutinefunction(func):
                return EnhancerFactory.create_async_before_wrapper(
                    target, before_enhancer, after_enhancer
                )

        return EnhancerFactory.create_before_wrapper(
            target, before_enhancer, after_enhancer
        )
