from functools import wraps

from src.database.connection import DatabaseError
from src.api.utils.response_helpers import error_response
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TabularProcessorError(Exception):
    """Base exception for tabular processor errors."""
    pass


class FileNotFoundError(TabularProcessorError):
    """Raised when the specified file does not exist."""
    pass


class UnsupportedFileTypeError(TabularProcessorError):
    """Raised when the file type is not supported."""
    pass


class FileReadError(TabularProcessorError):
    """Raised when a file cannot be read."""
    pass


class ValidationError(TabularProcessorError):
    """Raised when file validation fails."""
    pass


class EmptyFileError(TabularProcessorError):
    """Raised when the file contains no data."""
    pass


def handle_tabular_errors(f):
    """Decorator that maps tabular processing exceptions to HTTP responses."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except UnsupportedFileTypeError as e:
            logger.warning(f"Unsupported file type in {f.__name__}: {e}")
            return error_response(str(e), status_code=415)
        except FileNotFoundError as e:
            logger.warning(f"File not found in {f.__name__}: {e}")
            return error_response(str(e), status_code=404)
        except TabularProcessorError as e:
            logger.warning(f"Processing error in {f.__name__}: {e}")
            return error_response(str(e), status_code=422)
        except DatabaseError as e:
            logger.error(f"Database error in {f.__name__}: {e}")
            return error_response(f'Database error: {str(e)}', status_code=500)
        except Exception as e:
            logger.error(
                f"Unexpected error in {f.__name__}: {e}",
                exc_info=True
            )
            return error_response('An unexpected error occurred', status_code=500)
    return wrapper