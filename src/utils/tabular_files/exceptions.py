import logging
from functools import wraps

from src.database.connection import DatabaseError
from src.api.utils.response_helpers import error_response

logger = logging.getLogger(__name__)

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
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except UnsupportedFileTypeError as e:
            return error_response(str(e), status_code=415)  # Unsupported Media Type
        except FileNotFoundError as e:
            return error_response(str(e), status_code=404)
        except TabularProcessorError as e:
            return error_response(str(e), status_code=422)  # Unprocessable Entity
        except DatabaseError as e:
            return error_response(f'Database error: {str(e)}', status_code=500)
        except Exception as e:
            logger.exception(f'Unexpected error in import_file')
            return error_response('An unexpected error occurred', status_code=500)
    return wrapper