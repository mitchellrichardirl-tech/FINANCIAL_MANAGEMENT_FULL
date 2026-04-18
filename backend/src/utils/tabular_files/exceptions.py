"""
Exception types and error-mapping decorator for tabular file processing.

Defines a small exception hierarchy rooted at `TabularProcessorError`
and a `handle_tabular_errors` decorator that converts these exceptions
into API-layer `AppError` instances with appropriate HTTP status codes.

Used at the route level to separate tabular-processing concerns from
generic error handling — stack `@handle_tabular_errors` inside
`@handle_errors` so tabular exceptions get specific treatment while
everything else falls through to the generic handler.
"""

from functools import wraps

from src.api.utils.errors import AppError, ErrorCode
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TabularProcessorError(Exception):
    """Base exception for all tabular file processing errors.

    Catching this catches every exception defined in this module.
    """
    pass

# TODO: Maybe change this error n we don't overload the built-in FileNotFoundError? Or just make sure to import it with a different name if we need it.
class FileNotFoundError(TabularProcessorError):
    """Raised when the specified file does not exist.

    Note:
        Shadows Python's built-in `FileNotFoundError`. Inside this
        package the custom one is used; callers importing this module
        should be aware of the shadowing.
    """
    pass


class UnsupportedFileTypeError(TabularProcessorError):
    """Raised when the file extension is not recognised."""
    pass


class FileReadError(TabularProcessorError):
    """Raised when a file cannot be read (I/O, encoding, or format error)."""
    pass


class ValidationError(TabularProcessorError):
    """Raised when file contents fail validation constraints."""
    pass


class EmptyFileError(TabularProcessorError):
    """Raised when the file exists but contains no data rows."""
    pass


def handle_tabular_errors(f):
    """Decorator that converts tabular exceptions into API-layer `AppError`.

    Maps each `TabularProcessorError` subclass to an `AppError` with an
    appropriate HTTP status code and error code. Only handles
    tabular-specific exceptions — everything else (DatabaseError,
    ValueError, generic Exception) passes through untouched so it can
    be caught by the outer `@handle_errors` decorator.

    Mapping:
        UnsupportedFileTypeError → 415 Unsupported Media Type
        FileReadError            → 422 Unprocessable Entity
        TabularProcessorError    → 422 Unprocessable Entity (catch-all)

    Args:
        f: The route handler to wrap.

    Returns:
        Wrapped function that translates tabular exceptions.

    Example:
        @app.route('/upload', methods=['POST'])
        @handle_errors
        @handle_tabular_errors
        def upload_file():
            processor.validate(request.files['file'])
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)

        except UnsupportedFileTypeError as e:
            logger.warning(f"Unsupported file type in {f.__name__}: {e}")
            raise AppError(
                code=ErrorCode.INVALID_FORMAT,
                message=str(e),
                status_code=415,
                field='file',
            )

        except FileReadError as e:
            logger.warning(f"File read error in {f.__name__}: {e}")
            raise AppError(
                code=ErrorCode.INVALID_VALUE,
                message=str(e),
                status_code=422,
                field='file',
            )

        except TabularProcessorError as e:
            logger.warning(f"Processing error in {f.__name__}: {e}")
            raise AppError(
                code=ErrorCode.INVALID_VALUE,
                message=str(e),
                status_code=422,
                field='file',
            )

    return wrapper

