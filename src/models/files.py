from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone
import json
import numpy as np


class FileType(Enum):
    """Supported file types for tabular data."""
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
    """Column data types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """Information about a single column."""
    name: str
    index: int
    data_type: str
    nullable: bool
    sample_values: List[Any] = field(default_factory=list)
    null_count: int = 0
    unique_count: int = 0

    def __post_init__(self):
        """Convert numpy types to Python types."""
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
        return asdict(self)


@dataclass
class ValidationResult:
    """Result of file validation."""
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
        result = asdict(self)
        result['columns'] = [col.to_dict() if isinstance(col, ColumnInfo) else col 
                           for col in self.columns]
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class PreviewResult:
    """Result of file preview operation."""
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
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class ImportResult:
    """Result of data import operation."""
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
    warnings: List[str] = field(default_factory=list)
    imported_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass 
class SheetInfo:
    """Information about Excel sheets."""
    file_name: str
    sheet_names: List[str]
    sheet_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)