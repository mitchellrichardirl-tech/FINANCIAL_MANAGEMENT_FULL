import inspect
import logging
import functools
import time


class ContextLogger:
    """
    Logger wrapper that automatically includes class and method
    context in every log message via stack inspection.

    The module name is already included by the logging formatter
    via %(name)s, so the context prefix only adds:

    Class methods:  [ClassName.method_name] message
    Functions:      [function_name] message
    """

    def __init__(self, module_name: str):
        self._logger = logging.getLogger(module_name)
        self._module = module_name

    def _get_context(self) -> str:
        """Walk the call stack to determine the calling class and method."""
        frame = inspect.currentframe()
        try:
            # Up 2 frames: _get_context() -> log method() -> actual caller
            caller = frame.f_back.f_back
            method_name = caller.f_code.co_name
            local_vars = caller.f_locals

            if 'self' in local_vars:
                class_name = local_vars['self'].__class__.__name__
                return f"[{class_name}.{method_name}]"
            elif 'cls' in local_vars:
                class_name = local_vars['cls'].__name__
                return f"[{class_name}.{method_name}]"

            return f"[{method_name}]"
        finally:
            del frame

    def debug(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"{self._get_context()} {msg}", *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(f"{self._get_context()} {msg}", *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.WARNING):
            self._logger.warning(f"{self._get_context()} {msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.ERROR):
            self._logger.error(f"{self._get_context()} {msg}", *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        self._logger.exception(f"{self._get_context()} {msg}", *args, **kwargs)


def _extract_status_code(result) -> int:
    """Extract HTTP status code from a Flask route return value."""
    if isinstance(result, tuple) and len(result) >= 2:
        return result[1]
    if hasattr(result, 'status_code'):
        return result.status_code
    return 200


def log_route(logger: ContextLogger):
    """
    Decorator that automatically logs route entry, completion/failure,
    and elapsed time.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            prefix = f"[{func.__name__}]"
            path_params = kwargs or {}

            logger._logger.info(f"{prefix} Started | path_params={path_params}")
            start = time.time()

            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                status = _extract_status_code(result)
                logger._logger.info(
                    f"{prefix} Completed | status={status} | elapsed={elapsed:.3f}s"
                )
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger._logger.error(
                    f"{prefix} Failed | error={type(e).__name__}: {e} "
                    f"| elapsed={elapsed:.3f}s"
                )
                raise

        return wrapper
    return decorator