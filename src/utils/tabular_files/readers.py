from pathlib import Path
from typing import Optional, List, Union, Dict, Any
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


class FileReader:
    """Base class for reading tabular files."""
    
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
        
        if file_type in EXCEL_TYPES:
            return self._read_excel(
                file_path, file_type, nrows, skiprows, 
                usecols, header, names, sheet_name, **kwargs
            )
        elif file_type in TEXT_TYPES:
            return self._read_text(
                file_path, file_type, nrows, skiprows,
                usecols, header, names, **kwargs
            )
        elif file_type == FileType.PARQUET:
            return self._read_parquet(file_path, usecols, **kwargs)
        elif file_type == FileType.JSON:
            return self._read_json(file_path, nrows, **kwargs)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type: {file_type}")
    
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
        # Convert Path to string for better compatibility
        file_path_str = str(file_path)
        
        # Determine engine based on file type
        engine_map = {
            FileType.XLS: 'xlrd',        # Legacy Excel (BIFF format)
            FileType.XLSX: 'openpyxl',   # Modern Excel
            FileType.XLSM: 'openpyxl',   # Excel with macros
            FileType.XLSB: 'pyxlsb',     # Binary Excel
            FileType.ODS: 'odf',         # OpenDocument
        }
        
        engine = engine_map.get(file_type, 'openpyxl')
        
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
            # Handle missing engine gracefully
            engine_name = engine
            if 'xlrd' in str(e):
                raise FileReadError(
                    f"Cannot read .xls files: xlrd is not installed or not configured correctly. "
                    f"Install it with: pip install xlrd>=2.0.1"
                )
            elif 'openpyxl' in str(e):
                raise FileReadError(
                    f"Cannot read .xlsx files: openpyxl is not installed. "
                    f"Install it with: pip install openpyxl"
                )
            else:
                raise FileReadError(
                    f"Failed to read Excel file: Missing engine '{engine_name}'. "
                    f"Error: {str(e)}"
                )
        except Exception as e:
            raise FileReadError(f"Failed to read Excel file: {str(e)}")
    
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
        # Detect encoding if not specified
        encoding = self.encoding or detect_encoding(file_path)
        
        # Determine delimiter
        if self.delimiter:
            delimiter = self.delimiter
        elif file_type == FileType.TSV:
            delimiter = '\t'
        elif file_type == FileType.CSV:
            delimiter = ','
        else:
            delimiter = detect_delimiter(file_path, encoding)
        
        read_kwargs = {
            'delimiter': delimiter,
            'encoding': encoding,
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
        
        try:
            return pd.read_csv(file_path, **read_kwargs)
        except Exception as e:
            raise FileReadError(f"Failed to read text file: {str(e)}")
    
    def _read_parquet(
        self,
        file_path: Path,
        usecols: Optional[List[str]],
        **kwargs
    ) -> pd.DataFrame:
        """Read Parquet files."""
        try:
            return pd.read_parquet(file_path, columns=usecols, **kwargs)
        except Exception as e:
            raise FileReadError(f"Failed to read Parquet file: {str(e)}")
    
    def _read_json(
        self,
        file_path: Path,
        nrows: Optional[int],
        **kwargs
    ) -> pd.DataFrame:
        """Read JSON files."""
        try:
            df = pd.read_json(file_path, **kwargs)
            if nrows is not None:
                df = df.head(nrows)
            return df
        except Exception as e:
            raise FileReadError(f"Failed to read JSON file: {str(e)}")
    
    def get_sheet_names(self, file_path: Path) -> List[str]:
        """Get sheet names for Excel files."""
        try:
            excel_file = pd.ExcelFile(file_path)
            return excel_file.sheet_names
        except Exception:
            return []
    
    def count_rows(
        self,
        file_path: Path,
        file_type: FileType,
        has_header: bool = True
    ) -> int:
        """Count total rows in a file (excluding header)."""
        if file_type in TEXT_TYPES:
            encoding = self.encoding or detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                count = sum(1 for _ in f)
            return count - 1 if has_header else count
        else:
            # For other formats, read the entire file
            df = self.read(file_path, file_type)
            return len(df)