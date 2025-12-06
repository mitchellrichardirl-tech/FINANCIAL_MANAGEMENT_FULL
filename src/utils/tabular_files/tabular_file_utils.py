import os
from pathlib import Path
from typing import Optional, List, Any, Union, Dict
import chardet
import pandas as pd
import numpy as np
from datetime import datetime, date

from src.models.files import FileType, DataType


# File extension to FileType mapping
EXTENSION_MAP = {
    '.csv': FileType.CSV,
    '.tsv': FileType.TSV,
    '.txt': FileType.TXT,
    '.xls': FileType.XLS,
    '.xlsx': FileType.XLSX,
    '.xlsm': FileType.XLSM,
    '.xlsb': FileType.XLSB,
    '.ods': FileType.ODS,
    '.parquet': FileType.PARQUET,
    '.json': FileType.JSON,
}

EXCEL_TYPES = {FileType.XLS, FileType.XLSX, FileType.XLSM, FileType.XLSB, FileType.ODS}
TEXT_TYPES = {FileType.CSV, FileType.TSV, FileType.TXT}


def detect_file_type(file_path: Union[str, Path]) -> FileType:
    """Detect file type from extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    return EXTENSION_MAP.get(ext, FileType.UNKNOWN)


def detect_encoding(file_path: Union[str, Path], sample_size: int = 10000) -> str:
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    
    result = chardet.detect(raw_data)
    encoding = result.get('encoding', 'utf-8')
    
    # Fallback to utf-8 if detection fails or confidence is low
    if not encoding or result.get('confidence', 0) < 0.5:
        encoding = 'utf-8'
    
    return encoding


def detect_delimiter(
    file_path: Union[str, Path], 
    encoding: str = 'utf-8',
    sample_lines: int = 20
) -> str:
    """Auto-detect delimiter for text-based files."""
    import csv
    
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            # Read sample lines
            sample = ''.join(f.readline() for _ in range(sample_lines))
        
        # Use csv.Sniffer to detect delimiter
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except (csv.Error, Exception):
        # Default to comma if detection fails
        return ','


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)

def _is_date_column(sample: pd.Series) -> bool:
    """
    Check if a sample of values appears to be dates.
    
    Uses common date formats to avoid slow fallback parsing.
    """
    # Common date formats to try
    date_formats = [
        '%Y-%m-%d',           # 2023-01-15
        '%Y/%m/%d',           # 2023/01/15
        '%d-%m-%Y',           # 15-01-2023
        '%d/%m/%Y',           # 15/01/2023
        '%m-%d-%Y',           # 01-15-2023
        '%m/%d/%Y',           # 01/15/2023
        '%Y-%m-%d %H:%M:%S',  # 2023-01-15 10:30:00
        '%Y/%m/%d %H:%M:%S',  # 2023/01/15 10:30:00
        '%d-%m-%Y %H:%M:%S',  # 15-01-2023 10:30:00
        '%d/%m/%Y %H:%M:%S',  # 15/01/2023 10:30:00
        '%Y%m%d',             # 20230115
        '%d %b %Y',           # 15 Jan 2023
        '%d %B %Y',           # 15 January 2023
        '%b %d, %Y',          # Jan 15, 2023
        '%B %d, %Y',          # January 15, 2023
    ]
    
    # Need at least some values to check
    if len(sample) == 0:
        return False
    
    # All values must be strings
    if not all(isinstance(v, str) for v in sample):
        return False
    
    # Try each format
    for fmt in date_formats:
        try:
            pd.to_datetime(sample, format=fmt, errors='raise')
            return True
        except (ValueError, TypeError):
            continue
    
    return False

def infer_column_type(series: pd.Series) -> str:
    """Infer the data type of a pandas Series."""
    dtype = series.dtype
    
    if pd.api.types.is_integer_dtype(dtype):
        return DataType.INTEGER.value
    elif pd.api.types.is_float_dtype(dtype):
        return DataType.FLOAT.value
    elif pd.api.types.is_bool_dtype(dtype):
        return DataType.BOOLEAN.value
    elif pd.api.types.is_datetime64_any_dtype(dtype):
        return DataType.DATETIME.value
    elif pd.api.types.is_object_dtype(dtype):
        # Try to infer more specific type from string data
        non_null = series.dropna()
        if len(non_null) == 0:
            return DataType.STRING.value
        
        # Check if values can be parsed as dates
        if _is_date_column(non_null.head(100)):
            return DataType.DATE.value
        
        return DataType.STRING.value
    else:
        return DataType.UNKNOWN.value


def sanitize_for_json(value: Any) -> Any:
    """Convert a value to a JSON-serializable format."""
    if value is None:
        return None
    elif isinstance(value, (np.ndarray, pd.Series)):
        return value.tolist()
    elif isinstance(value, list):
        return [sanitize_for_json(v) for v in value]
    elif isinstance(value, dict):
        return {sanitize_for_json(k): sanitize_for_json(v) for k, v in value.items()}
    elif pd.isna(value):
        return None
    elif isinstance(value, (np.bool_, bool)):
        return bool(value)
    elif isinstance(value, (np.integer, int)):
        return int(value)
    elif isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    elif isinstance(value, (np.str_, str)):
        return value
    try:
        result = str(value)
        return result
    except Exception:
        return None

def dataframe_to_json_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert DataFrame to list of JSON-serializable dictionaries."""
    records = []
    
    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            record[str(col)] = sanitize_for_json(row[col])
        records.append(record)
    
    return records


def normalize_column_names(columns: List[str]) -> List[str]:
    """Normalize column names to be valid identifiers."""
    import re
    
    normalized = []
    seen = {}
    
    for col in columns:
        # Convert to string, strip whitespace and convert to lowercase
        name = str(col).strip().lower()
        
        # Replace invalid characters with underscores
        name = re.sub(r'[^\w\s-]', '_', name)
        name = re.sub(r'[-\s]+', '_', name)
        
        # Ensure it doesn't start with a number
        if name and name[0].isdigit():
            name = f"col_{name}"
        
        # Handle empty names
        if not name:
            name = "unnamed"
        
        # Handle duplicates
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        
        normalized.append(name)
    
    return normalized