"""
Tabular Data Processing Utility Module

A comprehensive utility for validating, previewing, and importing
tabular data from various file formats.

Supported formats:
    - CSV, TSV, TXT (text-based)
    - XLS, XLSX, XLSM, XLSB (Excel)
    - ODS (OpenDocument)
    - Parquet
    - JSON

Example usage:
    from tabular_processor import TabularProcessor
    
    processor = TabularProcessor()
    
    # Validate a file
    result = processor.validate("data.csv")
    print(result.to_json())
    
    # Preview data
    preview = processor.preview("data.csv", num_rows=5)
    print(preview.to_json())
    
    # Import with options
    data = processor.import_data(
        "data.xlsx",
        start_row=2,
        columns=["Name", "Age", "Email"],
        column_names=["full_name", "age_years", "email_address"]
    )
    print(data.to_json())
"""

from .processor import TabularProcessor
from src.models.files import (
    FileType,
    DataType,
    ValidationResult,
    PreviewResult,
    ImportResult,
    ColumnInfo,
    SheetInfo
)
from .exceptions import (
    TabularProcessorError,
    FileNotFoundError,
    UnsupportedFileTypeError,
    FileReadError,
    ValidationError,
    EmptyFileError
)

__version__ = "1.0.0"
__all__ = [
    "TabularProcessor",
    "FileType",
    "DataType", 
    "ValidationResult",
    "PreviewResult",
    "ImportResult",
    "ColumnInfo",
    "SheetInfo",
    "TabularProcessorError",
    "FileNotFoundError",
    "UnsupportedFileTypeError",
    "FileReadError",
    "ValidationError",
    "EmptyFileError",
]