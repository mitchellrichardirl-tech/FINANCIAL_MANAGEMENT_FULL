import csv
import os
import re
from pathlib import Path
from typing import Optional, List, Any, Union, Dict
from datetime import datetime, date

import chardet
import pandas as pd
import numpy as np

from src.models.files import FileType, DataType
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


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
    file_type = EXTENSION_MAP.get(ext, FileType.UNKNOWN)

    if file_type == FileType.UNKNOWN:
        logger.debug(f"Unknown file extension: {ext}")

    return file_type


def detect_encoding(file_path: Union[str, Path], sample_size: int = 10000) -> str:
    """Detect file encoding using chardet."""
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)

    result = chardet.detect(raw_data)
    encoding = result.get('encoding', 'utf-8')
    confidence = result.get('confidence', 0)

    if not encoding or confidence < 0.5:
        logger.debug(
            f"Low confidence encoding detection for {Path(file_path).name}: "
            f"detected={encoding}, confidence={confidence:.2f}, using utf-8"
        )
        encoding = 'utf-8'

    return encoding


def detect_delimiter(
    file_path: Union[str, Path],
    encoding: str = 'utf-8',
    sample_lines: int = 20
) -> str:
    """Auto-detect delimiter for text-based files."""
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            sample = ''.join(f.readline() for _ in range(sample_lines))

        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=',;\t|')
        return dialect.delimiter

    except (csv.Error, Exception) as e:
        logger.debug(
            f"Delimiter detection failed for {Path(file_path).name}: {e}, "
            f"defaulting to comma"
        )
        return ','


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path)


def _is_date_column(sample: pd.Series) -> bool:
    """
    Check if a sample of values appears to be dates.
    
    Uses common date formats to avoid slow fallback parsing.
    """
    date_formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%m-%d-%Y',
        '%m/%d/%Y',
        '%Y-%m-%d %H:%M:%S',
        '%Y/%m/%d %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
        '%d/%m/%Y %H:%M:%S',
        '%Y%m%d',
        '%d %b %Y',
        '%d %B %Y',
        '%b %d, %Y',
        '%B %d, %Y',
    ]

    if len(sample) == 0:
        return False

    if not all(isinstance(v, str) for v in sample):
        return False

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
        non_null = series.dropna()
        if len(non_null) == 0:
            return DataType.STRING.value

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
        return str(value)
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
    normalized = []
    seen = {}

    for col in columns:
        name = str(col).strip().lower()
        name = re.sub(r'[^\w\s-]', '_', name)
        name = re.sub(r'[-\s]+', '_', name)

        if name and name[0].isdigit():
            name = f"col_{name}"

        if not name:
            name = "unnamed"

        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0

        normalized.append(name)

    return normalized