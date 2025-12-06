from pathlib import Path
from typing import Optional, List, Union, Dict, Any
import pandas as pd
import numpy as np

from src.models.files import (
    FileType,
    ValidationResult,
    PreviewResult,
    ImportResult,
    ColumnInfo,
    SheetInfo
)
from src.utils.tabular_files.readers import FileReader
from src.utils.tabular_files.tabular_file_utils import (
    detect_file_type,
    detect_encoding,
    detect_delimiter,
    get_file_size,
    infer_column_type,
    dataframe_to_json_records,
    normalize_column_names,
    EXCEL_TYPES,
    TEXT_TYPES
)
from src.utils.tabular_files.exceptions import (
    TabularProcessorError,
    FileNotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
    EmptyFileError
)


class TabularProcessor:
    """
    Main class for processing tabular data files.
    
    Provides functionality for:
    - Validating tabular data files
    - Previewing file contents
    - Importing data with flexible column selection and naming
    
    Supports: CSV, TSV, TXT, XLS, XLSX, XLSM, XLSB, ODS, Parquet, JSON
    
    Example:
        processor = TabularProcessor()
        
        # Validate a file
        validation = processor.validate("data.csv")
        print(validation.to_json())
        
        # Preview first 10 rows
        preview = processor.preview("data.csv", num_rows=10)
        print(preview.to_json())
        
        # Import with options
        result = processor.import_data(
            "data.csv",
            start_row=5,
            columns=[0, 2, 4],
            column_names=["ID", "Name", "Value"]
        )
        print(result.to_json())
    """
    
    def __init__(
        self,
        default_encoding: Optional[str] = None,
        default_delimiter: Optional[str] = None,
        auto_detect_types: bool = True,
        normalize_columns: bool = False
    ):
        """
        Initialize the TabularProcessor.
        
        Args:
            default_encoding: Default encoding for text files (auto-detect if None)
            default_delimiter: Default delimiter for text files (auto-detect if None)
            auto_detect_types: Whether to auto-detect column data types
            normalize_columns: Whether to normalize column names to valid identifiers
        """
        self.default_encoding = default_encoding
        self.default_delimiter = default_delimiter
        self.auto_detect_types = auto_detect_types
        self.normalize_columns = normalize_columns
        
        self.reader = FileReader(
            encoding=default_encoding,
            delimiter=default_delimiter
        )
    
    def _validate_file_path(self, file_path: Union[str, Path]) -> Path:
        """Validate that file exists and return Path object."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Path is not a file: {path}")
        return path
    
    def _get_column_info(self, df: pd.DataFrame, sample_size: int = 5) -> List[ColumnInfo]:
        """Extract column information from DataFrame."""
        columns_info = []
        
        for idx, col in enumerate(df.columns):
            series = df[col]
            
            # Get sample values (non-null)
            non_null = series.dropna()
            sample_values = non_null.head(sample_size).tolist()
            
            col_info = ColumnInfo(
                name=str(col),
                index=int(idx),  # Ensure int
                data_type=infer_column_type(series) if self.auto_detect_types else "unknown",
                nullable=bool(series.isna().any()),  # Ensure bool
                sample_values=sample_values,
                null_count=int(series.isna().sum()),  # Ensure int
                unique_count=int(series.nunique())  # Ensure int
            )
            columns_info.append(col_info)
        
        return columns_info
    
    def validate(
        self,
        file_path: Union[str, Path],
        min_rows: int = 0,
        min_columns: int = 1,
        required_columns: Optional[List[str]] = None,
        sheet_name: Union[str, int] = 0
    ) -> ValidationResult:
        """
        Validate a file and return detailed information about its contents.
        
        Args:
            file_path: Path to the file to validate
            min_rows: Minimum required number of data rows
            min_columns: Minimum required number of columns
            required_columns: List of column names that must be present
            sheet_name: Sheet name or index for Excel files
            
        Returns:
            ValidationResult with validation status and file details
        """
        errors = []
        warnings = []
        
        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            return ValidationResult(
                is_valid=False,
                file_path=str(file_path),
                file_name=Path(file_path).name,
                file_type=FileType.UNKNOWN.value,
                file_size_bytes=0,
                row_count=0,
                column_count=0,
                columns=[],
                has_header=True,
                detected_delimiter=None,
                detected_encoding="unknown",
                errors=[str(e)],
                warnings=[]
            )
        
        # Detect file type
        file_type = detect_file_type(path)
        if file_type == FileType.UNKNOWN:
            return ValidationResult(
                is_valid=False,
                file_path=str(path),
                file_name=path.name,
                file_type=FileType.UNKNOWN.value,
                file_size_bytes=get_file_size(path),
                row_count=0,
                column_count=0,
                columns=[],
                has_header=True,
                detected_delimiter=None,
                detected_encoding="unknown",
                errors=[f"Unsupported file type: {path.suffix}"],
                warnings=[]
            )
        
        # Get file metadata
        file_size = get_file_size(path)
        encoding = detect_encoding(path) if file_type in TEXT_TYPES else "N/A"
        delimiter = detect_delimiter(path, encoding) if file_type in TEXT_TYPES else None
        
        try:
            # Read the file
            df = self.reader.read(
                path, 
                file_type, 
                sheet_name=sheet_name
            )
            
            row_count = len(df)
            column_count = len(df.columns)
            
            # Get column info
            columns_info = self._get_column_info(df)
            
            # Validation checks
            if row_count < min_rows:
                errors.append(
                    f"File has {row_count} data rows, minimum required: {min_rows}"
                )
            
            if column_count < min_columns:
                errors.append(
                    f"File has {column_count} columns, minimum required: {min_columns}"
                )
            
            if required_columns:
                actual_columns = set(str(c) for c in df.columns)
                missing = set(required_columns) - actual_columns
                if missing:
                    errors.append(f"Missing required columns: {list(missing)}")
            
            # Warnings
            if df.columns.duplicated().any():
                dup_cols = df.columns[df.columns.duplicated()].tolist()
                warnings.append(f"Duplicate column names detected: {dup_cols}")
            
            empty_cols = [col for col in df.columns if df[col].isna().all()]
            if empty_cols:
                warnings.append(f"Empty columns detected: {empty_cols}")
            
            # Check for completely empty rows
            empty_rows = df.isna().all(axis=1).sum()
            if empty_rows > 0:
                warnings.append(f"File contains {empty_rows} completely empty rows")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                file_path=str(path),
                file_name=path.name,
                file_type=file_type.value,
                file_size_bytes=file_size,
                row_count=row_count,
                column_count=column_count,
                columns=columns_info,
                has_header=True,
                detected_delimiter=delimiter,
                detected_encoding=encoding,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                file_path=str(path),
                file_name=path.name,
                file_type=file_type.value,
                file_size_bytes=file_size,
                row_count=0,
                column_count=0,
                columns=[],
                has_header=True,
                detected_delimiter=delimiter,
                detected_encoding=encoding,
                errors=[f"Failed to read file: {str(e)}"],
                warnings=[]
            )
    
    def preview(
        self,
        file_path: Union[str, Path],
        num_rows: int = 10,
        sheet_name: Union[str, int] = 0,
        include_types: bool = True
    ) -> PreviewResult:
        """
        Get a preview of the file contents.
        
        Args:
            file_path: Path to the file
            num_rows: Number of rows to include in preview
            sheet_name: Sheet name or index for Excel files
            include_types: Whether to include detected column types
            
        Returns:
            PreviewResult with preview data in JSON-serializable format
        """
        errors = []
        warnings = []
        
        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            return PreviewResult(
                success=False,
                file_name=Path(file_path).name,
                file_type=FileType.UNKNOWN.value,
                total_rows=0,
                total_columns=0,
                preview_row_count=0,
                columns=[],
                column_types={},
                data=[],
                errors=[str(e)]
            )
        
        file_type = detect_file_type(path)
        if file_type == FileType.UNKNOWN:
            return PreviewResult(
                success=False,
                file_name=path.name,
                file_type=FileType.UNKNOWN.value,
                total_rows=0,
                total_columns=0,
                preview_row_count=0,
                columns=[],
                column_types={},
                data=[],
                errors=[f"Unsupported file type: {path.suffix}"]
            )
        
        try:
            # Read full file to get total count, then limit preview
            df_full = self.reader.read(path, file_type, sheet_name=sheet_name)
            total_rows = len(df_full)
            
            # Get preview data
            df_preview = df_full.head(num_rows)
            
            # Normalize column names if requested
            columns = [str(c) for c in df_preview.columns]
            if self.normalize_columns:
                columns = normalize_column_names(columns)
                df_preview.columns = columns
            
            # Get column types
            column_types = {}
            if include_types:
                for col in df_preview.columns:
                    column_types[str(col)] = infer_column_type(df_preview[col])
            
            # Convert to JSON-serializable format
            data = dataframe_to_json_records(df_preview)
            
            return PreviewResult(
                success=True,
                file_name=path.name,
                file_type=file_type.value,
                total_rows=total_rows,
                total_columns=len(columns),
                preview_row_count=len(df_preview),
                columns=columns,
                column_types=column_types,
                data=data,
                errors=[],
                warnings=warnings
            )
            
        except Exception as e:
            return PreviewResult(
                success=False,
                file_name=path.name,
                file_type=file_type.value,
                total_rows=0,
                total_columns=0,
                preview_row_count=0,
                columns=[],
                column_types={},
                data=[],
                errors=[f"Failed to preview file: {str(e)}"]
            )
    
    def import_data(
        self,
        file_path: Union[str, Path],
        start_row: int = 0,
        columns: Optional[List[Union[int, str]]] = None,
        column_names: Optional[List[str]] = None,
        has_header: bool = True,
        sheet_name: Union[str, int] = 0,
        max_rows: Optional[int] = None,
        skip_empty_rows: bool = True,
        strip_whitespace: bool = True
    ) -> ImportResult:
        """
        Import data from a tabular file with flexible options.
        
        Args:
            file_path: Path to the file
            start_row: Row to start importing from (0-based index, after header if present)
            columns: List of column indices (int) or names (str) to import. 
                     None imports all columns.
            column_names: Custom names for imported columns. If provided, must match
                         the number of columns being imported.
            has_header: Whether the file has a header row
            sheet_name: Sheet name or index for Excel files
            max_rows: Maximum number of rows to import (None = all)
            skip_empty_rows: Whether to skip completely empty rows
            strip_whitespace: Whether to strip whitespace from string values
            
        Returns:
            ImportResult with imported data in JSON-serializable format
        """
        errors = []
        warnings = []
        
        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            return ImportResult(
                success=False,
                file_name=Path(file_path).name,
                file_type=FileType.UNKNOWN.value,
                start_row=start_row,
                rows_imported=0,
                rows_skipped=0,
                columns_imported=[],
                columns_requested=columns,
                column_mapping=None,
                data=[],
                errors=[str(e)]
            )
        
        file_type = detect_file_type(path)
        if file_type == FileType.UNKNOWN:
            return ImportResult(
                success=False,
                file_name=path.name,
                file_type=FileType.UNKNOWN.value,
                start_row=start_row,
                rows_imported=0,
                rows_skipped=0,
                columns_imported=[],
                columns_requested=columns,
                column_mapping=None,
                data=[],
                errors=[f"Unsupported file type: {path.suffix}"]
            )
        
        try:
            # Calculate skiprows based on start_row and header settings
            skiprows = None
            if start_row > 0:
                skiprows = list(range(0, start_row - 1))
            header_setting = 0 if has_header else None
                        
            # Process column selection
            usecols = None
            if columns is not None:
                usecols = columns
            
            # Read the file
            df = self.reader.read(
                path,
                file_type,
                nrows=max_rows,
                skiprows=skiprows,
                usecols=usecols,
                header=header_setting,
                sheet_name=sheet_name
            )
            
            rows_before = len(df)
            
            # Skip empty rows if requested
            if skip_empty_rows:
                df = df.dropna(how='all')
            
            rows_skipped = rows_before - len(df)
            
            # Strip whitespace if requested
            if strip_whitespace:
                for col in df.select_dtypes(include=['object']).columns:
                    df[col] = df[col].apply(
                        lambda x: x.strip() if isinstance(x, str) else x
                    )
            
            # Apply custom column names
            original_columns = [str(c) for c in df.columns]
            column_mapping = None
            
            if column_names is not None:
                if len(column_names) != len(df.columns):
                    warnings.append(
                        f"Column names count ({len(column_names)}) doesn't match "
                        f"data columns ({len(df.columns)}). Adjusting..."
                    )
                    # Pad or truncate
                    if len(column_names) < len(df.columns):
                        column_names = list(column_names) + [
                            f"column_{i}" for i in range(len(column_names), len(df.columns))
                        ]
                    else:
                        column_names = column_names[:len(df.columns)]
                
                column_mapping = dict(zip(original_columns, column_names))
                df.columns = column_names
            elif self.normalize_columns:
                new_columns = normalize_column_names(original_columns)
                column_mapping = dict(zip(original_columns, new_columns))
                df.columns = new_columns
            
            # Convert to JSON-serializable format
            final_columns = [str(c) for c in df.columns]
            data = dataframe_to_json_records(df)
            
            return ImportResult(
                success=True,
                file_name=path.name,
                file_type=file_type.value,
                start_row=start_row,
                rows_imported=len(df),
                rows_skipped=rows_skipped + start_row,
                columns_imported=final_columns,
                columns_requested=columns,
                column_mapping=column_mapping,
                data=data,
                errors=[],
                warnings=warnings
            )
            
        except Exception as e:
            return ImportResult(
                success=False,
                file_name=path.name,
                file_type=file_type.value,
                start_row=start_row,
                rows_imported=0,
                rows_skipped=0,
                columns_imported=[],
                columns_requested=columns,
                column_mapping=None,
                data=[],
                errors=[f"Failed to import file: {str(e)}"]
            )
    
    def get_sheet_info(self, file_path: Union[str, Path]) -> SheetInfo:
        """
        Get sheet information for Excel files.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            SheetInfo with sheet names
        """
        path = self._validate_file_path(file_path)
        sheet_names = self.reader.get_sheet_names(path)
        
        return SheetInfo(
            file_name=path.name,
            sheet_names=sheet_names,
            sheet_count=len(sheet_names)
        )
    
    def is_tabular(self, file_path: Union[str, Path]) -> bool:
        """
        Quick check if a file appears to be valid tabular data.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file appears to be valid tabular data
        """
        try:
            validation = self.validate(file_path, min_rows=0, min_columns=1)
            return validation.is_valid
        except Exception:
            return False