"""
Data models for tabular file operations.

Defines the data classes and enums used throughout the file-import
pipeline — from initial validation through preview to final import.
Each stage produces a typed result object that captures the outcome,
metadata, and any errors or warnings.

Typical flow:
    1. Validate file → `ValidationResult` (with `ColumnInfo` per column)
    2. Preview rows → `PreviewResult`
    3. Import data → `ImportResult`

All result classes support `to_dict()` and `to_json()` for API
serialization.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone
import json
import numpy as np


class FileType(Enum):
    """Supported file types for tabular data uploads.

    Used to determine which reader to use when parsing an uploaded file.
    Mapped from file extensions during validation.

    Members:
        CSV, TSV, TXT: Delimited text formats.
        XLS, XLSX, XLSM, XLSB: Excel formats (legacy and modern).
        ODS: OpenDocument spreadsheet.
        PARQUET: Columnar binary format.
        JSON: JSON array/records.
        UNKNOWN: Fallback for unrecognised extensions.
    """
    CSV = "csv"
    TSV = "tsv"
    TXT = "txt"
    XLS = "xls"
    XLSX = "xlsx"
    XLSM = "xlsm"
    XLSB = "xlsb"
    ODS = "ods"
    PARQUET = "parquet"
    JSON = "json"
    UNKNOWN = "unknown"


class DataType(Enum):
    """Detected column data types.

    Assigned during validation by inspecting column values. Used in
    `ColumnInfo` and displayed in the file-preview UI to help users
    understand what was detected.

    Members:
        STRING: Text / catch-all.
        INTEGER: Whole numbers.
        FLOAT: Decimal numbers.
        BOOLEAN: True/False values.
        DATE: Date without time component.
        DATETIME: Date with time component.
        UNKNOWN: Could not be determined.
    """
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """Metadata about a single column in a tabular file.

    Built during validation and included in `ValidationResult.columns`.
    Provides enough information for the UI to let users select or rename
    columns before import.

    Attributes:
        name: Column header text.
        index: Zero-based positional index in the source file.
        data_type: Detected type as a string (see `DataType`).
        nullable: Whether the column contains any null values.
        sample_values: A handful of representative non-null values.
        null_count: Total number of null/missing cells.
        unique_count: Number of distinct non-null values.
    """
    name: str
    index: int
    data_type: str
    nullable: bool
    sample_values: List[Any] = field(default_factory=list)
    null_count: int = 0
    unique_count: int = 0

    def __post_init__(self):
        """Coerce numpy scalar types to native Python types.

        Pandas operations often return numpy types (`np.bool_`,
        `np.int64`, etc.) which don't serialize cleanly to JSON. This
        converts them at construction time so downstream code doesn't
        need to worry about it.
        """
        # Convert nullable to Python bool
        if isinstance(self.nullable, (np.bool_, np.generic)):
            self.nullable = bool(self.nullable)

        # Convert counts to Python int
        if isinstance(self.null_count, (np.integer, np.generic)):
            self.null_count = int(self.null_count)

        if isinstance(self.unique_count, (np.integer, np.generic)):
            self.unique_count = int(self.unique_count)

        # Convert index to Python int
        if isinstance(self.index, (np.integer, np.generic)):
            self.index = int(self.index)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON serialization."""
        return asdict(self)


@dataclass
class ValidationResult:
    """Outcome of validating an uploaded tabular file.

    Captures file metadata, detected format properties, per-column info,
    and any errors or warnings. Used by the preview step and returned to
    the UI so the user can confirm before importing.

    Attributes:
        is_valid: True if the file can be imported (no blocking errors).
        file_path: Absolute path to the stored file on disk.
        file_name: Original filename as uploaded by the user.
        file_type: Detected `FileType` value (as a string).
        file_size_bytes: File size in bytes.
        row_count: Number of data rows (excluding header).
        column_count: Number of columns detected.
        columns: Per-column metadata (see `ColumnInfo`).
        has_header: Whether a header row was detected.
        detected_delimiter: Delimiter character for delimited text files.
            None for binary formats.
        detected_encoding: Character encoding (e.g. "utf-8").
        errors: Blocking issues that prevent import.
        warnings: Non-blocking issues the user should be aware of.
        validated_at: ISO 8601 timestamp of when validation ran.
    """
    is_valid: bool
    file_path: str
    file_name: str
    file_type: str
    file_size_bytes: int
    row_count: int
    column_count: int
    columns: List[ColumnInfo]
    has_header: bool
    detected_delimiter: Optional[str]
    detected_encoding: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict, ensuring nested `ColumnInfo` objects are expanded."""
        result = asdict(self)
        result['columns'] = [col.to_dict() if isinstance(col, ColumnInfo) else col
                           for col in self.columns]
        return result

    def to_json(self) -> str:
        """Serialize to a formatted JSON string.

        Uses `default=str` to handle any remaining non-serializable
        types (e.g. `Path` objects).
        """
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class PreviewResult:
    """Outcome of a file preview operation.

    Contains a slice of the file's data (typically the first N rows)
    along with column names and types. Returned to the UI so the user
    can inspect the data before committing to an import.

    Attributes:
        success: True if the preview was generated without errors.
        file_name: Original filename.
        file_type: Detected file type.
        total_rows: Total rows in the file (not just the preview).
        total_columns: Total column count.
        preview_row_count: Number of rows included in `data`.
        columns: Column header names.
        column_types: Mapping of column name → detected type string.
        data: List of row dicts representing the preview slice.
        errors: Issues encountered during preview generation.
        warnings: Non-blocking observations.
        generated_at: ISO 8601 timestamp.
    """
    success: bool
    file_name: str
    file_type: str
    total_rows: int
    total_columns: int
    preview_row_count: int
    columns: List[str]
    column_types: Dict[str, str]
    data: List[Dict[str, Any]]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class ImportResult:
    """Outcome of importing tabular data into the database.

    Produced at the end of the import pipeline and returned to the UI
    as a summary of what was imported. Includes the actual imported data
    so the UI can display it immediately without a second round-trip.

    Attributes:
        success: True if the import completed without blocking errors.
        file_name: Original filename.
        file_type: Detected file type.
        start_row: First row index that was imported (supports
            skipping header/preamble rows).
        rows_imported: Number of rows successfully written to the DB.
        rows_skipped: Number of rows skipped (e.g. due to validation).
        columns_imported: Column names that were actually written.
        columns_requested: Column names/indices the user asked for, if
            a subset was selected. None if all columns were imported.
        column_mapping: User-provided rename mapping
            `{original_name: new_name}`, or None if no renaming.
        data: The imported rows as dicts.
        upload_id: FK to the `uploads` table row, if the data was
            persisted.
        errors: Blocking issues encountered during import.
        warnings: Non-blocking issues or per-row warnings. May contain
            strings or structured dicts.
        imported_at: ISO 8601 timestamp.
    """
    success: bool
    file_name: str
    file_type: str
    start_row: int
    rows_imported: int
    rows_skipped: int
    columns_imported: List[str]
    columns_requested: Optional[List[Any]]
    column_mapping: Optional[Dict[str, str]]
    data: List[Dict[str, Any]]
    upload_id: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str | Dict[str, Any]] = field(default_factory=list)
    imported_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class SheetInfo:
    """Metadata about the sheets in an Excel workbook.

    Returned when a user uploads a multi-sheet Excel file so the UI can
    prompt them to choose which sheet to import.

    Attributes:
        file_name: Original filename of the workbook.
        sheet_names: Ordered list of sheet names in the workbook.
        sheet_count: Number of sheets.
    """
    file_name: str
    sheet_names: List[str]
    sheet_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation suitable for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to a formatted JSON string."""
        return json.dumps(self.to_dict(), indent=2)