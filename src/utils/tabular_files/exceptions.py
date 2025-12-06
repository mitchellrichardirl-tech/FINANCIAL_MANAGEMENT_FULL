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