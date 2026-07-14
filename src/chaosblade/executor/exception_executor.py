"""ThrowExceptionExecutor - injects exceptions into method calls.

Equivalent to Java's DefaultThrowCustomException.
Flags:
  - exception: exception class name (e.g., "RuntimeError", "redis.exceptions.ConnectionError")
  - exception-message: message for the exception (optional)
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.enhancer_model import EnhancerModel

from chaosblade.common.exception.interrupt_process import throw_immediately

logger = logging.getLogger(__name__)

# Flag names
FLAG_EXCEPTION = "exception"
FLAG_EXCEPTION_MESSAGE = "exception-message"

# Built-in exception mapping for convenience
_BUILTIN_EXCEPTIONS: dict[str, type] = {
    "Exception": Exception,
    "RuntimeError": RuntimeError,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "IOError": IOError,
    "OSError": OSError,
    "TimeoutError": TimeoutError,
    "ConnectionError": ConnectionError,
    "ConnectionRefusedError": ConnectionRefusedError,
    "ConnectionResetError": ConnectionResetError,
    "FileNotFoundError": FileNotFoundError,
    "PermissionError": PermissionError,
    "MemoryError": MemoryError,
    "KeyError": KeyError,
    "AttributeError": AttributeError,
    "ImportError": ImportError,
    "NotImplementedError": NotImplementedError,
}


class ThrowExceptionExecutor:
    """Executor that throws a specified exception from the target method.

    Resolves the exception class by name:
    1. Check built-in exceptions (e.g., "RuntimeError")
    2. Try to import as a fully qualified class path (e.g., "redis.exceptions.ConnectionError")
    3. Fall back to generic RuntimeError with the class name in the message
    """

    def run(self, enhancer_model: EnhancerModel) -> None:
        """Execute the exception injection.

        Reads 'exception' and 'exception-message' from action flags,
        resolves the exception class, and raises InterruptProcessException
        with THROWS_IMMEDIATELY state.
        """
        exception_name = enhancer_model.get_action_flag(FLAG_EXCEPTION)
        message = enhancer_model.get_action_flag(FLAG_EXCEPTION_MESSAGE) or ""

        if not exception_name:
            # Default to RuntimeError if no exception specified
            exception_name = "RuntimeError"
            if not message:
                message = "chaosblade inject fault"

        # Resolve exception class
        exception_cls = self._resolve_exception_class(exception_name)

        # Create the exception instance
        try:
            exc = exception_cls(message) if message else exception_cls()
        except Exception:
            exc = RuntimeError(f"{exception_name}: {message}")

        logger.debug("Injecting exception: %s(%s)", exception_cls.__name__, message)

        # Throw via InterruptProcessException
        throw_immediately(exc)

    def _resolve_exception_class(self, name: str) -> type:
        """Resolve an exception class from its name.

        Args:
            name: Simple name (e.g., "RuntimeError") or
                  qualified path (e.g., "redis.exceptions.ConnectionError")

        Returns:
            The exception class, or RuntimeError as fallback.
        """
        # 1. Check builtin exceptions
        if name in _BUILTIN_EXCEPTIONS:
            return _BUILTIN_EXCEPTIONS[name]

        # 2. Try as qualified import path
        if "." in name:
            module_path, _, class_name = name.rpartition(".")
            try:
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name, None)
                if cls is not None and isinstance(cls, type) and issubclass(cls, BaseException):
                    return cls
            except (ImportError, AttributeError):
                logger.debug("Could not import exception class: %s", name)

        # 3. Try as builtins
        import builtins
        cls = getattr(builtins, name, None)
        if cls is not None and isinstance(cls, type) and issubclass(cls, BaseException):
            return cls

        # 4. Fallback
        logger.warning("Could not resolve exception '%s', using RuntimeError", name)
        return RuntimeError
