from functools import wraps

from src.api.utils.errors import AppError, ErrorCode
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
    """
    Decorator that maps tabular processing exceptions to AppError.
    
    Only handles tabular-specific exceptions. All other errors (DatabaseError,
    ValueError, etc.) pass through to @handle_errors.
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