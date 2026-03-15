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
    """Reads tabular files into pandas DataFrames."""

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
        """Read a file into a DataFrame."""
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
        """Read Excel file formats."""
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
        """
        Build an ordered list of encodings to attempt.

        The order matters:
        1. Whatever the detector returned (trust it first)
        2. utf-8 — the modern default, covers most files
        3. utf-8-sig — handles Windows UTF-8 files with BOM
        4. cp1252 — extremely common for bank/financial exports on Windows,
            and a superset of latin-1 for printable characters
        5. latin-1 — never raises UnicodeDecodeError (maps every byte 0-255),
            so it acts as a guaranteed last resort, though it may decode
            some characters incorrectly

        Duplicates are removed while preserving order so we don't waste
        time retrying the same encoding.
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
        """Read text-based files (CSV, TSV, TXT)."""
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
        """Read Parquet files."""
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
        """Read JSON files."""
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
        """Get sheet names for Excel files."""
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
        """Count total rows in a file (excluding header)."""
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