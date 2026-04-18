"""
Multi-format tabular file reading.

Provides the `FileReader` class, which reads CSV, TSV, Excel, Parquet,
and JSON files into pandas DataFrames with automatic encoding/delimiter
detection and graceful fallback for common encoding mismatches.

The core value-add over calling `pd.read_*` directly is the encoding
fallback chain for text files — financial exports from banks frequently
claim to be ASCII or UTF-8 but are actually Windows-1252, and this
class handles that transparently.
"""

from pathlib import Path
from typing import Optional, List, Union
import pandas as pd

from src.models.files import FileType
from src.utils.tabular_files.tabular_file_utils import (
    detect_file_type,
    detect_encoding,
    detect_delimiter,
    EXCEL_TYPES,
    TEXT_TYPES
)
from .exceptions import FileReadError, UnsupportedFileTypeError
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class FileReader:
    """Reads tabular files of various formats into pandas DataFrames.

    Dispatches to the appropriate pandas reader based on `FileType`
    and handles format-specific concerns: Excel engine selection,
    text-file encoding detection with fallback, and helpful error
    messages for missing optional dependencies.

    Encoding and delimiter can be overridden at construction; otherwise
    they're auto-detected per file.

    Class Attributes:
        EXCEL_ENGINE_MAP: Maps Excel `FileType` members to the pandas
            engine name required to read them. Each engine is a
            separate pip dependency.

    Attributes:
        encoding: Override encoding for text files. If None, each file
            is auto-detected.
        delimiter: Override delimiter for text files. If None, inferred
            from file type (TSV → tab, CSV → comma) or auto-detected
            for TXT.
    """

    # Engine selection for Excel formats
    EXCEL_ENGINE_MAP = {
        FileType.XLS: 'xlrd',
        FileType.XLSX: 'openpyxl',
        FileType.XLSM: 'openpyxl',
        FileType.XLSB: 'pyxlsb',
        FileType.ODS: 'odf',
    }

    def __init__(
        self,
        encoding: Optional[str] = None,
        delimiter: Optional[str] = None
    ):
        """Initialize with optional encoding and delimiter overrides.

        Args:
            encoding: Force this encoding for all text files. If None,
                each file is detected independently via `chardet`.
            delimiter: Force this delimiter for all text files. If
                None, inferred from `FileType` or auto-detected.
        """
        self.encoding = encoding
        self.delimiter = delimiter

    def read(
        self,
        file_path: Path,
        file_type: FileType,
        nrows: Optional[int] = None,
        skiprows: Optional[Union[int, List[int]]] = None,
        usecols: Optional[List[Union[int, str]]] = None,
        header: Optional[int] = 0,
        names: Optional[List[str]] = None,
        sheet_name: Union[str, int] = 0,
        **kwargs
    ) -> pd.DataFrame:
        """Read a tabular file into a DataFrame.

        Dispatches to the format-specific reader based on `file_type`.
        Most parameters mirror the pandas `read_*` APIs and are passed
        through as-is.

        Args:
            file_path: Path to the file.
            file_type: Detected `FileType` — determines which reader
                is used.
            nrows: Maximum number of rows to read. None for all.
            skiprows: Rows to skip at the start. Can be a count (int)
                or a list of specific row indices.
            usecols: Subset of columns to read, by index or name.
            header: Row index to use as column names. 0 for first row,
                None if the file has no header.
            names: Explicit column names to use. If provided alongside
                `header=0`, the header row is consumed but replaced.
            sheet_name: For Excel files, which sheet to read (by name
                or zero-based index). Ignored for other formats.
            **kwargs: Additional arguments passed directly to the
                underlying pandas reader.

        Returns:
            The loaded DataFrame.

        Raises:
            UnsupportedFileTypeError: If `file_type` is not supported.
            FileReadError: If reading fails for any reason (missing
                engine, encoding issues, malformed file, etc.).
        """
        logger.debug(
            f"Reading {file_path.name}: type={file_type.value}, "
            f"nrows={nrows}, skiprows={skiprows}, usecols={usecols}"
        )

        if file_type in EXCEL_TYPES:
            df = self._read_excel(
                file_path, file_type, nrows, skiprows,
                usecols, header, names, sheet_name, **kwargs
            )
        elif file_type in TEXT_TYPES:
            df = self._read_text(
                file_path, file_type, nrows, skiprows,
                usecols, header, names, **kwargs
            )
        elif file_type == FileType.PARQUET:
            df = self._read_parquet(file_path, usecols, **kwargs)
        elif file_type == FileType.JSON:
            df = self._read_json(file_path, nrows, **kwargs)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type: {file_type}")

        logger.debug(
            f"Read {file_path.name}: {len(df)} rows, {len(df.columns)} columns"
        )
        return df

    def _read_excel(
        self,
        file_path: Path,
        file_type: FileType,
        nrows: Optional[int],
        skiprows: Optional[Union[int, List[int]]],
        usecols: Optional[List[Union[int, str]]],
        header: Optional[int],
        names: Optional[List[str]],
        sheet_name: Union[str, int],
        **kwargs
    ) -> pd.DataFrame:
        """Read an Excel-family file with the appropriate engine.

        Selects the engine from `EXCEL_ENGINE_MAP` and calls
        `pd.read_excel()`. Missing-engine `ImportError`s are caught
        and re-raised with a pip install hint.

        Args:
            file_path: Path to the file.
            file_type: Specific Excel variant — determines the engine.
            nrows, skiprows, usecols, header, names, sheet_name:
                Passed through to `pd.read_excel()`.
            **kwargs: Additional `pd.read_excel()` arguments.

        Returns:
            The loaded DataFrame.

        Raises:
            FileReadError: If the required engine is not installed or
                the file cannot be read.
        """
        file_path_str = str(file_path)
        engine = self.EXCEL_ENGINE_MAP.get(file_type, 'openpyxl')

        logger.debug(f"Reading Excel {file_path.name}: engine={engine}, sheet={sheet_name}")

        read_kwargs = {
            'sheet_name': sheet_name,
            'engine': engine,
            'header': header,
        }

        if nrows is not None:
            read_kwargs['nrows'] = nrows
        if skiprows is not None:
            read_kwargs['skiprows'] = skiprows
        if usecols is not None:
            read_kwargs['usecols'] = usecols
        if names is not None:
            read_kwargs['names'] = names

        read_kwargs.update(kwargs)

        try:
            return pd.read_excel(file_path_str, **read_kwargs)
        except ImportError as e:
            error_str = str(e)
            if 'xlrd' in error_str:
                msg = (
                    "Cannot read .xls files: xlrd is not installed. "
                    "Install with: pip install xlrd>=2.0.1"
                )
            elif 'openpyxl' in error_str:
                msg = (
                    "Cannot read .xlsx files: openpyxl is not installed. "
                    "Install with: pip install openpyxl"
                )
            else:
                msg = f"Missing engine '{engine}': {error_str}"

            logger.error(f"Excel engine not available for {file_path.name}: {msg}")
            raise FileReadError(msg)
        except Exception as e:
            logger.error(f"Failed to read Excel {file_path.name}: {e}")
            raise FileReadError(f"Failed to read Excel file: {str(e)}")

    @staticmethod
    def _build_encoding_fallback_chain(detected: str) -> list[str]:
        """Build an ordered list of encodings to try when reading text.

        The order matters:
            1. Whatever the detector returned — trust it first.
            2. utf-8 — the modern default, covers most files.
            3. utf-8-sig — handles Windows UTF-8 files with BOM.
            4. cp1252 — extremely common for bank/financial exports
               from Windows, and a superset of latin-1 for printable
               characters.
            5. latin-1 — never raises `UnicodeDecodeError` (maps every
               byte 0–255), so it's a guaranteed last resort, though
               it may decode some characters incorrectly.

        Duplicates are removed (with normalisation, so "UTF-8" and
        "utf8" collapse) while preserving order, so we don't retry
        the same encoding.

        Args:
            detected: The encoding returned by `detect_encoding()`.

        Returns:
            Ordered, deduplicated list of encoding names to try.
        """
        candidates = [
            detected,
            'utf-8',
            'utf-8-sig',
            'cp1252',
            'latin-1',
        ]

        # Normalize for deduplication: 'ASCII' and 'ascii' are the same,
        # 'utf8' and 'utf-8' should collapse, etc.
        seen = set()
        chain = []
        for enc in candidates:
            normalized = enc.lower().replace('-', '').replace('_', '')
            if normalized not in seen:
                seen.add(normalized)
                chain.append(enc)

        return chain

    def _read_text(
        self,
        file_path: Path,
        file_type: FileType,
        nrows: Optional[int],
        skiprows: Optional[Union[int, List[int]]],
        usecols: Optional[List[Union[int, str]]],
        header: Optional[int],
        names: Optional[List[str]],
        **kwargs
    ) -> pd.DataFrame:
        """Read a delimited text file (CSV, TSV, TXT) with encoding fallback.

        Determines encoding and delimiter (using instance overrides,
        file-type defaults, or auto-detection), then attempts
        `pd.read_csv()` with each encoding in the fallback chain until
        one succeeds. Only encoding errors trigger fallback — other
        exceptions (missing file, malformed structure) fail
        immediately since a different encoding won't fix them.

        Args:
            file_path: Path to the file.
            file_type: CSV, TSV, or TXT — determines default delimiter.
            nrows, skiprows, usecols, header, names: Passed through to
                `pd.read_csv()`.
            **kwargs: Additional `pd.read_csv()` arguments.

        Returns:
            The loaded DataFrame.

        Raises:
            FileReadError: If all encodings fail, or if a non-encoding
                error occurs.
        """
        encoding = self.encoding or detect_encoding(file_path)

        if self.delimiter:
            delimiter = self.delimiter
        elif file_type == FileType.TSV:
            delimiter = '\t'
        elif file_type == FileType.CSV:
            delimiter = ','
        else:
            delimiter = detect_delimiter(file_path, encoding)

        logger.debug(
            f"Reading text file {file_path.name}: "
            f"encoding={encoding}, delimiter={delimiter!r}"
        )

        read_kwargs = {
            'delimiter': delimiter,
            'header': header,
            'on_bad_lines': 'warn',
            'low_memory': False,
        }

        if nrows is not None:
            read_kwargs['nrows'] = nrows
        if skiprows is not None:
            read_kwargs['skiprows'] = skiprows
        if usecols is not None:
            read_kwargs['usecols'] = usecols
        if names is not None:
            read_kwargs['names'] = names
            if header == 0:
                read_kwargs['header'] = None

        read_kwargs.update(kwargs)

        # Build an ordered list of encodings to try.
        # Start with the detected one, then fall through sensible defaults.
        # This handles the very common case where chardet/charset-normalizer
        # returns 'ascii' for a file that's actually Windows-1252.
        encodings_to_try = self._build_encoding_fallback_chain(encoding)

        last_error = None
        for enc in encodings_to_try:
            try:
                read_kwargs['encoding'] = enc
                df = pd.read_csv(file_path, **read_kwargs)

                if enc != encoding:
                    logger.warning(
                        f"Detected encoding '{encoding}' failed for "
                        f"{file_path.name}, successfully read with '{enc}'"
                    )

                return df

            except (UnicodeDecodeError, UnicodeError) as e:
                logger.debug(
                    f"Encoding '{enc}' failed for {file_path.name}: {e}"
                )
                last_error = e
                continue

            except Exception as e:
                # Non-encoding errors should not trigger fallback —
                # a missing file, malformed CSV structure, etc. is not
                # going to be fixed by trying a different encoding
                logger.error(
                    f"Failed to read text file {file_path.name}: {e}"
                )
                raise FileReadError(f"Failed to read text file: {str(e)}")

        # All encodings exhausted
        logger.error(
            f"All encodings failed for {file_path.name}. "
            f"Tried: {encodings_to_try}. Last error: {last_error}"
        )
        raise FileReadError(
            f"Failed to read text file with any encoding. "
            f"Tried: {', '.join(encodings_to_try)}. "
            f"Last error: {str(last_error)}"
        )

    def _read_parquet(
        self,
        file_path: Path,
        usecols: Optional[List[str]],
        **kwargs
    ) -> pd.DataFrame:
        """Read a Parquet file.

        Args:
            file_path: Path to the file.
            usecols: Optional column subset to read.
            **kwargs: Additional `pd.read_parquet()` arguments.

        Returns:
            The loaded DataFrame.

        Raises:
            FileReadError: If reading fails.
        """
        logger.debug(f"Reading Parquet: {file_path.name}")

        try:
            return pd.read_parquet(file_path, columns=usecols, **kwargs)
        except Exception as e:
            logger.error(f"Failed to read Parquet {file_path.name}: {e}")
            raise FileReadError(f"Failed to read Parquet file: {str(e)}")

    def _read_json(
        self,
        file_path: Path,
        nrows: Optional[int],
        **kwargs
    ) -> pd.DataFrame:
        """Read a JSON file.

        `pd.read_json()` doesn't support `nrows`, so it's applied
        after loading via `.head()`.

        Args:
            file_path: Path to the file.
            nrows: If provided, truncate to this many rows after
                loading.
            **kwargs: Additional `pd.read_json()` arguments.

        Returns:
            The loaded (possibly truncated) DataFrame.

        Raises:
            FileReadError: If reading fails.
        """
        logger.debug(f"Reading JSON: {file_path.name}")

        try:
            df = pd.read_json(file_path, **kwargs)
            if nrows is not None:
                df = df.head(nrows)
            return df
        except Exception as e:
            logger.error(f"Failed to read JSON {file_path.name}: {e}")
            raise FileReadError(f"Failed to read JSON file: {str(e)}")

    def get_sheet_names(self, file_path: Path) -> List[str]:
        """List sheet names in an Excel workbook.

        Args:
            file_path: Path to the Excel file.

        Returns:
            List of sheet names in file order. Empty list if the file
            cannot be read (logged as a warning, not raised).
        """
        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names

            logger.debug(f"Found {len(sheet_names)} sheets in {file_path.name}")
            return sheet_names
        except Exception as e:
            logger.warning(f"Failed to read sheets from {file_path.name}: {e}")
            return []

    def count_rows(
        self,
        file_path: Path,
        file_type: FileType,
        has_header: bool = True
    ) -> int:
        """Count data rows in a file without loading it fully.

        For text files, counts lines directly (with encoding fallback),
        which is much faster than loading into a DataFrame for large
        files. Other formats are loaded and measured with `len()`.

        Args:
            file_path: Path to the file.
            file_type: Determines which counting strategy to use.
            has_header: If True, subtract one from the line count for
                text files. Ignored for non-text formats since pandas
                handles the header there.

        Returns:
            Number of data rows (header excluded if `has_header=True`).
        """
        logger.debug(f"Counting rows in {file_path.name}")

        if file_type in TEXT_TYPES:
            encoding = self.encoding or detect_encoding(file_path)
            encodings = self._build_encoding_fallback_chain(encoding)

            count = None
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc, errors='replace') as f:
                        count = sum(1 for _ in f)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if count is None:
                # errors='replace' with latin-1 should never fail,
                # but handle it defensively
                with open(file_path, 'rb') as f:
                    count = sum(1 for _ in f)

            result = count - 1 if has_header else count
        else:
            df = self.read(file_path, file_type)
            result = len(df)

        logger.debug(f"Row count for {file_path.name}: {result}")
        return result