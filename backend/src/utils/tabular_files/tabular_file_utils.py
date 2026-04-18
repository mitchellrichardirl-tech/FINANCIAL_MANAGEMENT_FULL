"""
Utility functions for tabular file handling.

Low-level helpers used by the tabular-file readers and processors:
file-type / encoding / delimiter detection, column type inference,
JSON serialization for pandas/numpy types, and column-name
normalization.

These are stateless, pure functions — no classes or module state.
"""

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


# Maps file extensions to `FileType` enum members.
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

# File types that are read via the Excel reader path.
EXCEL_TYPES = {FileType.XLS, FileType.XLSX, FileType.XLSM, FileType.XLSB, FileType.ODS}

# File types that are delimited text and need encoding/delimiter detection.
TEXT_TYPES = {FileType.CSV, FileType.TSV, FileType.TXT}


def detect_file_type(file_path: Union[str, Path]) -> FileType:
    """Determine file type from the extension.

    Purely extension-based — does not inspect file contents. Unknown
    extensions return `FileType.UNKNOWN` rather than raising.

    Args:
        file_path: Path to the file. Only the suffix is used.

    Returns:
        The corresponding `FileType` enum member, or
        `FileType.UNKNOWN` if the extension is not recognised.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    file_type = EXTENSION_MAP.get(ext, FileType.UNKNOWN)

    if file_type == FileType.UNKNOWN:
        logger.debug(f"Unknown file extension: {ext}")

    return file_type


def detect_encoding(file_path: Union[str, Path], sample_size: int = 10000) -> str:
    """Detect the character encoding of a text file.

    Reads a sample of bytes from the start of the file and uses
    `chardet` to guess the encoding. Falls back to UTF-8 if detection
    fails or confidence is below 50%.

    Args:
        file_path: Path to the file.
        sample_size: Number of bytes to read for detection. Defaults
            to 10 KB — larger samples are more accurate but slower.

    Returns:
        Encoding name suitable for passing to `open(encoding=...)`.
        Always returns a valid encoding (falls back to "utf-8").
    """
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
    """Auto-detect the field delimiter in a delimited text file.

    Reads the first `sample_lines` and uses `csv.Sniffer` to guess
    the delimiter from a candidate set (comma, semicolon, tab, pipe).
    Falls back to comma on failure.

    Args:
        file_path: Path to the file.
        encoding: Character encoding to read with. Typically the
            result of `detect_encoding()`.
        sample_lines: Number of lines to inspect. Defaults to 20.

    Returns:
        The detected delimiter character, or "," if detection fails.
    """
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
    """Return the file size in bytes.

    Thin wrapper around `os.path.getsize()` for consistency with the
    other helpers in this module.

    Args:
        file_path: Path to the file.

    Returns:
        File size in bytes.
    """
    return os.path.getsize(file_path)


def _is_date_column(sample: pd.Series) -> bool:
    """Check whether a sample of string values all parse as dates.

    Tries a fixed list of common date formats against the entire
    sample. Uses explicit formats rather than pandas' inference mode,
    which is slow and noisy on non-date strings.

    All sample values must be strings and all must parse with the
    same format for this to return True.

    Args:
        sample: A slice of string values from a column.

    Returns:
        True if every value parses successfully with one of the
        known formats; False otherwise.
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
    """Infer a `DataType` for a pandas Series.

    Maps pandas dtypes to the application's `DataType` enum. For
    object-dtype columns (the catch-all for strings), additionally
    checks whether the values look like dates using
    `_is_date_column()` on the first 100 non-null values.

    Args:
        series: The column to inspect.

    Returns:
        A `DataType` enum value (as a string).
    """
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
    """Recursively convert a value to a JSON-serializable form.

    Handles numpy scalars, pandas types, datetimes, bytes, and nested
    containers. NaN/Inf/NaT become None. Used when converting
    DataFrame rows for API responses, since `json.dumps` can't handle
    numpy/pandas types natively.

    Args:
        value: Any value, potentially nested.

    Returns:
        A JSON-safe equivalent (None, bool, int, float, str, list,
        or dict). Falls back to `str(value)` for unrecognised types,
        or None if that also fails.

    Note:
        The check order matters — container checks come before the
        `pd.isna()` check because `pd.isna()` raises on lists/arrays.
    """
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
    """Convert a DataFrame to a list of JSON-safe row dicts.

    Similar to `df.to_dict(orient='records')` but runs each value
    through `sanitize_for_json()` so the result is guaranteed safe
    for `json.dumps()`.

    Args:
        df: The DataFrame to convert.

    Returns:
        List of dicts, one per row, with string column names and
        JSON-serializable values.
    """
    records = []

    for _, row in df.iterrows():
        record = {}
        for col in df.columns:
            record[str(col)] = sanitize_for_json(row[col])
        records.append(record)

    return records


def normalize_column_names(columns: List[str]) -> List[str]:
    """Convert column names to valid, unique, lowercase identifiers.

    Transforms arbitrary column headers into safe identifiers by:
        1. Lowercasing and stripping whitespace.
        2. Replacing non-word characters with underscores.
        3. Collapsing runs of dashes/spaces into single underscores.
        4. Prefixing `col_` if the name starts with a digit.
        5. Replacing empty names with "unnamed".
        6. Appending `_1`, `_2`, etc. to resolve duplicates.

    Args:
        columns: Original column names (may contain spaces, special
            characters, duplicates, etc.).

    Returns:
        List of normalized names, same length and order as the input.

    Example:
        >>> normalize_column_names(['First Name', 'First Name', '2024 Total', ''])
        ['first_name', 'first_name_1', 'col_2024_total', 'unnamed']
    """
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