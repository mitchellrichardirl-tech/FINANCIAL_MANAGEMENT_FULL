"""
Context-aware logging with automatic caller identification.

Provides `ContextLogger`, a thin wrapper around the standard `logging`
module that automatically prefixes messages with the calling class and
method name via stack inspection. Also provides a `log_route` decorator
for automatic entry/exit/timing logs on Flask route handlers.

Usage:
    from src.utils.logging import ContextLogger

    logger = ContextLogger(__name__)

    class MyService:
        def do_work(self):
            logger.info("starting")  # → [MyService.do_work] starting

Log output format (set by `setup_logging()`):
    2024-01-15 10:30:45 | INFO     | src.api.routes.accounts | [AccountRepository.get_all] Retrieved 5 accounts
"""

import inspect
import logging
from logging.handlers import RotatingFileHandler
import functools
import time
from typing import Optional

LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

class ContextLogger:
    """Logger wrapper that auto-prefixes messages with caller context.

    Uses stack inspection to determine the calling class and method
    at log time, producing messages like `[ClassName.method] text`.
    The module name is handled separately by the formatter's `%(name)s`
    field, so the context prefix is class/method only.

    Stack inspection happens on every call, guarded by `isEnabledFor()`
    checks so disabled log levels skip the inspection overhead entirely.

    Example output prefixes:
        Class method:    [ReceiptRepository.save]
        Classmethod:     [SchemaManager.init_db]
        Module function: [migrate]
    """

    def __init__(self, module_name: str, level: str = 'DEBUG'):
        """Create a context logger for the given module.

        Args:
            module_name: Dotted module path, typically `__name__`.
                Passed through to `logging.getLogger()` so the standard
                logger hierarchy and level configuration apply.
        """
        self._logger = logging.getLogger(module_name)
        self._module = module_name
        self._level = level.upper()

    def _get_context(self) -> str:
        """Walk the call stack to find the calling class and method.

        Looks two frames up (past this method and the log wrapper) to
        find the actual caller. Detects class context by checking for
        `self` or `cls` in the caller's locals.

        Returns:
            Bracketed context string: `[ClassName.method]` for methods,
            `[function_name]` for module-level functions.

        Note:
            The frame reference is explicitly deleted in a `finally`
            block to avoid reference cycles that would delay garbage
            collection — a standard precaution when using
            `inspect.currentframe()`.
        """
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

    @staticmethod
    def setup_logging(level: Optional[str] = 'DEBUG'):
        """Configure root logger with console and rotating file handlers.

        Call once at application startup. Sets up:
            - Console handler (stdout) at DEBUG level.
            - Rotating file handler writing to `app.log`, rotating at
              10 MB with 5 backup files retained.

        Both handlers use the same pipe-delimited format:
            `timestamp | LEVEL | module.name | message`
        """
        # Console output
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))

        # File output — this is what actually saves logs
        file_handler = RotatingFileHandler(
            "app.log", maxBytes=10_000_000, backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
        if level:
            if level.upper() in LEVELS:
                logging_level = LEVELS[level.upper()]
            else:
                logging.warning(f"Invalid logging level '{level}', defaulting to DEBUG")
                logging_level = logging.DEBUG
        logging.basicConfig(
            level=logging_level,
            handlers=[console, file_handler]
        )

    def debug(self, msg: str, *args, **kwargs):
        """Log a DEBUG message with caller context prepended."""
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"{self._get_context()} {msg}", *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log an INFO message with caller context prepended."""
        if self._logger.isEnabledFor(logging.INFO):
            self._logger.info(f"{self._get_context()} {msg}", *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log a WARNING message with caller context prepended."""
        if self._logger.isEnabledFor(logging.WARNING):
            self._logger.warning(f"{self._get_context()} {msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log an ERROR message with caller context prepended."""
        if self._logger.isEnabledFor(logging.ERROR):
            self._logger.error(f"{self._get_context()} {msg}", *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log an ERROR message with caller context and exception traceback.

        Should only be called from within an `except` block — the
        current exception info is captured automatically.
        """
        self._logger.exception(f"{self._get_context()} {msg}", *args, **kwargs)

    def set_level(self, level: str):
        """Set the logger's level by name (e.g., 'DEBUG', 'INFO')."""
        if level.upper() not in LEVELS:
            raise ValueError(f"Invalid logging level: {level}")
        self._logger.setLevel(LEVELS[level.upper()])
        self._logger.info(f"Logging level set to {level.upper()}")

def _extract_status_code(result) -> int:
    """Extract an HTTP status code from a Flask route return value.

    Flask routes can return a bare response, a `(body, status)` tuple,
    or a `Response` object. This handles all three shapes.

    Args:
        result: Whatever the route handler returned.

    Returns:
        The HTTP status code, defaulting to 200 if none can be
        determined.
    """
    if isinstance(result, tuple) and len(result) >= 2:
        return result[1]
    if hasattr(result, 'status_code'):
        return result.status_code
    return 200


def log_route(logger: ContextLogger):
    """Decorator that logs Flask route entry, exit, and elapsed time.

    Wraps a route handler to emit an INFO log on entry (with path
    params), an INFO log on successful completion (with status code
    and timing), or an ERROR log on exception (with exception type,
    message, and timing). Exceptions are re-raised after logging.

    Bypasses `ContextLogger._get_context()` since the decorated
    function's name is already known — uses `[func_name]` directly
    as the prefix.

    Args:
        logger: The `ContextLogger` to write to.

    Returns:
        A decorator that wraps the route handler.

    Example:
        @app.route('/accounts/<int:account_id>')
        @log_route(logger)
        def get_account(account_id):
            ...

        # Produces:
        #   [get_account] Started | path_params={'account_id': 5}
        #   [get_account] Completed | status=200 | elapsed=0.023s
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