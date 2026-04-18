"""
High-level tabular file processing: validate, preview, import.

Provides `TabularProcessor`, the main entry point for the file-upload
workflow. Wraps the lower-level `FileReader` with result objects that
capture errors gracefully rather than raising — designed for direct
use by API routes where every outcome should produce a structured
response.

Three-stage workflow:
    1. `validate()` — check the file is readable and meets basic
       constraints; return detailed metadata and any issues.
    2. `preview()` — show the user the first N rows so they can
       confirm before importing.
    3. `import_data()` — read the full file with column selection,
       renaming, and cleaning options.

All three return typed result objects (`ValidationResult`,
`PreviewResult`, `ImportResult`) with `errors` and `warnings` lists —
check `is_valid` / `success` rather than expecting exceptions.
"""

from pathlib import Path
from typing import Optional, List, Union
import pandas as pd

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
    TEXT_TYPES
)
from src.utils.tabular_files.exceptions import FileNotFoundError
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TabularProcessor:
    """Orchestrates validation, preview, and import of tabular files.

    The public methods never raise for file-level problems (missing
    file, wrong format, read failure). Instead they return result
    objects with `is_valid=False` / `success=False` and a populated
    `errors` list. This keeps API routes simple — every code path
    produces a serializable response.

    Attributes:
        default_encoding: Override encoding passed to the underlying
            `FileReader`. None for auto-detection.
        default_delimiter: Override delimiter for text files. None for
            auto-detection / file-type defaults.
        auto_detect_types: If True, run type inference on each column
            during validation. If False, all columns report "unknown".
        normalize_columns: If True, column names are normalised to
            valid identifiers (lowercase, underscores) during preview
            and import.
        reader: The underlying `FileReader` instance.
    """

    def __init__(
        self,
        default_encoding: Optional[str] = None,
        default_delimiter: Optional[str] = None,
        auto_detect_types: bool = True,
        normalize_columns: bool = False
    ):
        """Initialize with optional defaults and behaviour flags.

        Args:
            default_encoding: Force this encoding for all text files.
                None for per-file auto-detection.
            default_delimiter: Force this delimiter for all text files.
                None for per-file inference.
            auto_detect_types: Whether to run type inference during
                validation. Defaults to True; disable for speed on
                very wide files.
            normalize_columns: Whether to normalise column names
                during preview and import. Defaults to False to
                preserve original headers.
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
        """Check that a path exists and points to a regular file.

        Args:
            file_path: Path to check.

        Returns:
            The path as a resolved `Path` object.

        Raises:
            FileNotFoundError: If the path doesn't exist or isn't a
                file. Caught by the public methods and folded into
                result-object errors.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Path is not a file: {path}")
        return path

    def _get_column_info(self, df: pd.DataFrame, sample_size: int = 5) -> List[ColumnInfo]:
        """Build `ColumnInfo` objects for every column in a DataFrame.

        Computes type (if `auto_detect_types`), nullability, null
        count, unique count, and a small sample of non-null values
        for each column.

        Args:
            df: The DataFrame to inspect.
            sample_size: Number of sample values to capture per column.
                Defaults to 5.

        Returns:
            List of `ColumnInfo`, one per column, in column order.
        """
        columns_info = []

        for idx, col in enumerate(df.columns):
            series = df[col]

            non_null = series.dropna()
            sample_values = non_null.head(sample_size).tolist()

            col_info = ColumnInfo(
                name=str(col),
                index=int(idx),
                data_type=infer_column_type(series) if self.auto_detect_types else "unknown",
                nullable=bool(series.isna().any()),
                sample_values=sample_values,
                null_count=int(series.isna().sum()),
                unique_count=int(series.nunique())
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
        """Validate a tabular file and collect metadata about it.

        Reads the entire file, checks it against the given constraints,
        and returns a `ValidationResult` with detailed column info and
        any errors or warnings.

        Checks that produce errors (block import):
            - File not found or not readable.
            - Unsupported file type.
            - Fewer than `min_rows` data rows.
            - Fewer than `min_columns` columns.
            - Any `required_columns` missing.

        Checks that produce warnings (import proceeds):
            - Duplicate column names.
            - Completely empty columns.
            - Completely empty rows.

        Args:
            file_path: Path to the file to validate.
            min_rows: Minimum data rows required. Defaults to 0.
            min_columns: Minimum columns required. Defaults to 1.
            required_columns: Column names that must be present. If
                None, no column-presence check is performed.
            sheet_name: For Excel files, which sheet to validate.
                Defaults to the first sheet.

        Returns:
            A `ValidationResult` with `is_valid` indicating whether
            all checks passed, plus metadata, per-column info, and
            populated `errors` / `warnings` lists.
        """
        errors = []
        warnings = []

        logger.debug(
            f"Validating file: {Path(file_path).name} "
            f"| min_rows={min_rows}, min_columns={min_columns}"
        )

        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            logger.warning(f"Validation failed — file not found: {file_path}")
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

        file_type = detect_file_type(path)
        if file_type == FileType.UNKNOWN:
            logger.warning(f"Unsupported file type: {path.suffix}")
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

        file_size = get_file_size(path)
        encoding = detect_encoding(path) if file_type in TEXT_TYPES else "N/A"
        delimiter = detect_delimiter(path, encoding) if file_type in TEXT_TYPES else None

        logger.debug(
            f"File metadata: type={file_type.value}, size={file_size}, "
            f"encoding={encoding}, delimiter={delimiter!r}"
        )

        try:
            df = self.reader.read(
                path,
                file_type,
                sheet_name=sheet_name
            )

            row_count = len(df)
            column_count = len(df.columns)
            columns_info = self._get_column_info(df)

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

            if df.columns.duplicated().any():
                dup_cols = df.columns[df.columns.duplicated()].tolist()
                warnings.append(f"Duplicate column names detected: {dup_cols}")

            empty_cols = [col for col in df.columns if df[col].isna().all()]
            if empty_cols:
                warnings.append(f"Empty columns detected: {empty_cols}")

            empty_rows = df.isna().all(axis=1).sum()
            if empty_rows > 0:
                warnings.append(f"File contains {empty_rows} completely empty rows")

            is_valid = len(errors) == 0

            if is_valid:
                logger.debug(
                    f"Validation passed for {path.name}: "
                    f"{row_count} rows, {column_count} columns"
                )
            else:
                logger.debug(
                    f"Validation failed for {path.name}: {errors}"
                )

            if warnings:
                logger.debug(f"Validation warnings for {path.name}: {warnings}")

            return ValidationResult(
                is_valid=is_valid,
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
            logger.error(f"Failed to read file for validation {path.name}: {e}")
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
        """Generate a preview of the first N rows of a file.

        Reads the full file (to get an accurate total row count), then
        slices the first `num_rows` for the preview data. Column names
        are normalised if `self.normalize_columns` is True.

        Args:
            file_path: Path to the file.
            num_rows: Number of rows to include in the preview.
                Defaults to 10.
            sheet_name: For Excel files, which sheet to preview.
            include_types: Whether to run type inference on preview
                columns. Defaults to True.

        Returns:
            A `PreviewResult` with the preview data as JSON-safe row
            dicts, plus column names, types, and total counts.
            `success=False` with populated `errors` if the file can't
            be read.
        """
        errors = []
        warnings = []

        logger.debug(f"Previewing file: {Path(file_path).name} | num_rows={num_rows}")

        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            logger.warning(f"Preview failed — file not found: {file_path}")
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
            logger.warning(f"Preview failed — unsupported file type: {path.suffix}")
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
            df_full = self.reader.read(path, file_type, sheet_name=sheet_name)
            total_rows = len(df_full)

            df_preview = df_full.head(num_rows)

            columns = [str(c) for c in df_preview.columns]
            if self.normalize_columns:
                columns = normalize_column_names(columns)
                df_preview.columns = columns

            column_types = {}
            if include_types:
                for col in df_preview.columns:
                    column_types[str(col)] = infer_column_type(df_preview[col])

            data = dataframe_to_json_records(df_preview)

            logger.debug(
                f"Preview generated for {path.name}: "
                f"{total_rows} total rows, {len(columns)} columns, "
                f"showing {len(df_preview)} rows"
            )

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
            logger.error(f"Failed to preview {path.name}: {e}")
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
        """Import data from a file with column selection and renaming.

        Reads the file with the requested slicing, applies cleaning
        transforms, optionally renames or normalises columns, and
        returns the data as JSON-safe row dicts.

        Args:
            file_path: Path to the file.
            start_row: Zero-based row index to start reading from.
                Rows before this are skipped. Defaults to 0.
            columns: Subset of columns to import, by name or index.
                None for all columns.
            column_names: Replacement column names. If the count
                doesn't match, names are padded with `column_N` or
                truncated, and a warning is added.
            has_header: Whether the file has a header row. Defaults
                to True.
            sheet_name: For Excel files, which sheet to import.
            max_rows: Maximum data rows to import. None for all.
            skip_empty_rows: If True (default), drop rows where every
                column is null.
            strip_whitespace: If True (default), strip leading/trailing
                whitespace from string values.

        Returns:
            An `ImportResult` with the imported data, counts, and
            `column_mapping` dict showing original → new names if
            renaming occurred. `success=False` with populated `errors`
            if the import fails.
        """
        errors = []
        warnings = []

        logger.debug(
            f"Importing file: {Path(file_path).name} "
            f"| start_row={start_row}, has_header={has_header}, "
            f"columns={columns}, max_rows={max_rows}"
        )

        try:
            path = self._validate_file_path(file_path)
        except FileNotFoundError as e:
            logger.warning(f"Import failed — file not found: {file_path}")
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
            logger.warning(f"Import failed — unsupported file type: {path.suffix}")
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
            skiprows = None
            if start_row > 0:
                skiprows = list(range(0, start_row - 1))
            header_setting = 0 if has_header else None

            usecols = None
            if columns is not None:
                usecols = columns

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

            if skip_empty_rows:
                df = df.dropna(how='all')

            rows_skipped = rows_before - len(df)

            if rows_skipped > 0:
                logger.debug(f"Skipped {rows_skipped} empty rows from {path.name}")

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
                    msg = (
                        f"Column names count ({len(column_names)}) doesn't match "
                        f"data columns ({len(df.columns)}). Adjusting..."
                    )
                    warnings.append(msg)
                    logger.warning(f"Import {path.name}: {msg}")

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

            final_columns = [str(c) for c in df.columns]
            data = dataframe_to_json_records(df)

            logger.debug(
                f"Imported {path.name}: {len(df)} rows, "
                f"{len(final_columns)} columns "
                f"(skipped={rows_skipped + start_row})"
            )

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
            logger.error(f"Failed to import {path.name}: {e}")
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
        """Return sheet metadata for an Excel workbook.

        Used by the UI to present a sheet-selection dropdown when the
        user uploads a multi-sheet file.

        Args:
            file_path: Path to an Excel file.

        Returns:
            `SheetInfo` with the list of sheet names and count. If the
            file can't be read as Excel, `sheet_names` will be empty.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        path = self._validate_file_path(file_path)
        sheet_names = self.reader.get_sheet_names(path)

        logger.debug(f"Sheet info for {path.name}: {len(sheet_names)} sheets")

        return SheetInfo(
            file_name=path.name,
            sheet_names=sheet_names,
            sheet_count=len(sheet_names)
        )

    def is_tabular(self, file_path: Union[str, Path]) -> bool:
        """Quickly check whether a file is readable as tabular data.

        Convenience wrapper around `validate()` that returns a bare
        boolean. Any exception during validation is caught and
        treated as False.

        Args:
            file_path: Path to the file.

        Returns:
            True if the file validates with at least one column,
            False otherwise.
        """
        try:
            validation = self.validate(file_path, min_rows=0, min_columns=1)
            return validation.is_valid
        except Exception:
            return False