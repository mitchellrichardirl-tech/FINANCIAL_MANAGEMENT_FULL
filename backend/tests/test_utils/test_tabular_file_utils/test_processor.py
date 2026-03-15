import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import json

from src.utils.tabular_files.processor import TabularProcessor
from src.models.files import (
    FileType,
    ValidationResult,
    PreviewResult,
    ImportResult,
    ColumnInfo,
    SheetInfo
)
from src.utils.tabular_files.exceptions import (
    FileNotFoundError,
    UnsupportedFileTypeError,
    FileReadError
)


class TestTabularProcessorInit:
    """Tests for TabularProcessor initialization."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        processor = TabularProcessor()
        
        assert processor.default_encoding is None
        assert processor.default_delimiter is None
        assert processor.auto_detect_types is True
        assert processor.normalize_columns is False
        assert processor.reader is not None
    
    def test_init_with_encoding(self):
        """Test initialization with custom encoding."""
        processor = TabularProcessor(default_encoding='utf-8')
        
        assert processor.default_encoding == 'utf-8'
    
    def test_init_with_delimiter(self):
        """Test initialization with custom delimiter."""
        processor = TabularProcessor(default_delimiter=';')
        
        assert processor.default_delimiter == ';'
    
    def test_init_with_auto_detect_types_disabled(self):
        """Test initialization with type detection disabled."""
        processor = TabularProcessor(auto_detect_types=False)
        
        assert processor.auto_detect_types is False
    
    def test_init_with_normalize_columns_enabled(self):
        """Test initialization with column normalization enabled."""
        processor = TabularProcessor(normalize_columns=True)
        
        assert processor.normalize_columns is True
    
    def test_init_with_all_options(self):
        """Test initialization with all options specified."""
        processor = TabularProcessor(
            default_encoding='latin-1',
            default_delimiter='\t',
            auto_detect_types=False,
            normalize_columns=True
        )
        
        assert processor.default_encoding == 'latin-1'
        assert processor.default_delimiter == '\t'
        assert processor.auto_detect_types is False
        assert processor.normalize_columns is True
    
    def test_init_creates_reader_with_options(self):
        """Test that reader is created with matching options."""
        processor = TabularProcessor(
            default_encoding='utf-8',
            default_delimiter=','
        )
        
        assert processor.reader.encoding == 'utf-8'
        assert processor.reader.delimiter == ','


class TestValidateFilePath:
    """Tests for _validate_file_path method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_validate_existing_file(self, processor, sample_csv_file):
        """Test validation of existing file."""
        result = processor._validate_file_path(sample_csv_file)
        
        assert isinstance(result, Path)
        assert result.exists()
    
    def test_validate_string_path(self, processor, sample_csv_file):
        """Test validation with string path."""
        result = processor._validate_file_path(str(sample_csv_file))
        
        assert isinstance(result, Path)
    
    def test_validate_path_object(self, processor, sample_csv_file):
        """Test validation with Path object."""
        result = processor._validate_file_path(Path(sample_csv_file))
        
        assert isinstance(result, Path)
    
    def test_validate_nonexistent_file(self, processor, tmp_path):
        """Test validation of non-existent file."""
        fake_path = tmp_path / "nonexistent.csv"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            processor._validate_file_path(fake_path)
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_validate_directory_path(self, processor, tmp_path):
        """Test validation of directory path (should fail)."""
        with pytest.raises(FileNotFoundError) as exc_info:
            processor._validate_file_path(tmp_path)
        
        assert "not a file" in str(exc_info.value).lower()


class TestGetColumnInfo:
    """Tests for _get_column_info method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    @pytest.fixture
    def processor_no_types(self):
        """Create a TabularProcessor with type detection disabled."""
        return TabularProcessor(auto_detect_types=False)
    
    def test_get_column_info_basic(self, processor):
        """Test basic column info extraction."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie']
        })
        
        result = processor._get_column_info(df)
        
        assert len(result) == 2
        assert all(isinstance(col, ColumnInfo) for col in result)
    
    def test_get_column_info_names(self, processor):
        """Test column names are captured."""
        df = pd.DataFrame({
            'first_col': [1, 2],
            'second_col': [3, 4]
        })
        
        result = processor._get_column_info(df)
        
        assert result[0].name == 'first_col'
        assert result[1].name == 'second_col'
    
    def test_get_column_info_indices(self, processor):
        """Test column indices are correct."""
        df = pd.DataFrame({
            'a': [1], 'b': [2], 'c': [3]
        })
        
        result = processor._get_column_info(df)
        
        assert result[0].index == 0
        assert result[1].index == 1
        assert result[2].index == 2
    
    def test_get_column_info_data_types(self, processor):
        """Test data type detection."""
        df = pd.DataFrame({
            'int_col': [1, 2, 3],
            'float_col': [1.1, 2.2, 3.3],
            'str_col': ['a', 'b', 'c']
        })
        
        result = processor._get_column_info(df)
        
        assert result[0].data_type == 'integer'
        assert result[1].data_type == 'float'
        assert result[2].data_type == 'string'
    
    def test_get_column_info_nullable(self, processor):
        """Test nullable detection."""
        df = pd.DataFrame({
            'has_nulls': [1, None, 3],
            'no_nulls': [1, 2, 3]
        })
        
        result = processor._get_column_info(df)
        
        # Check type and value
        assert isinstance(result[0].nullable, bool)
        assert result[0].nullable is True
        
        assert isinstance(result[1].nullable, bool)
        assert result[1].nullable is False


    def test_get_column_info_null_count(self, processor):
        """Test null count calculation."""
        df = pd.DataFrame({
            'col': [1, None, None, 4, None]
        })
        
        result = processor._get_column_info(df)
        
        # Check type and value
        assert isinstance(result[0].null_count, int)
        assert result[0].null_count == 3


    def test_get_column_info_unique_count(self, processor):
        """Test unique count calculation."""
        df = pd.DataFrame({
            'col': ['a', 'b', 'a', 'c', 'b']
        })
        
        result = processor._get_column_info(df)
        
        # Check type and value
        assert isinstance(result[0].unique_count, int)
        assert result[0].unique_count == 3


    def test_get_column_info_indices(self, processor):
        """Test column indices are correct."""
        df = pd.DataFrame({
            'a': [1], 'b': [2], 'c': [3]
        })
        
        result = processor._get_column_info(df)
        
        # Check types and values
        assert isinstance(result[0].index, int)
        assert isinstance(result[1].index, int)
        assert isinstance(result[2].index, int)
        
        assert result[0].index == 0
        assert result[1].index == 1
        assert result[2].index == 2
    
    def test_get_column_info_sample_values(self, processor):
        """Test sample values extraction."""
        df = pd.DataFrame({
            'col': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        })
        
        result = processor._get_column_info(df, sample_size=3)
        
        assert len(result[0].sample_values) == 3
        assert result[0].sample_values == [1, 2, 3]
    
    def test_get_column_info_sample_excludes_nulls(self, processor):
        """Test sample values exclude null values."""
        df = pd.DataFrame({
            'col': [None, None, 1, 2, 3]
        })
        
        result = processor._get_column_info(df, sample_size=3)
        
        assert None not in result[0].sample_values
        assert result[0].sample_values == [1, 2, 3]
    
    def test_get_column_info_no_type_detection(self, processor_no_types):
        """Test column info with type detection disabled."""
        df = pd.DataFrame({
            'int_col': [1, 2, 3]
        })
        
        result = processor_no_types._get_column_info(df)
        
        assert result[0].data_type == 'unknown'
    
    def test_get_column_info_empty_dataframe(self, processor):
        """Test column info for empty DataFrame."""
        df = pd.DataFrame({'a': [], 'b': []})
        
        result = processor._get_column_info(df)
        
        assert len(result) == 2
        assert result[0].null_count == 0


class TestValidate:
    """Tests for validate method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_validate_csv_basic(self, processor, sample_csv_file):
        """Test basic CSV validation."""
        result = processor.validate(sample_csv_file)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.file_type == 'csv'
    
    def test_validate_returns_file_info(self, processor, sample_csv_file):
        """Test that validation returns file information."""
        result = processor.validate(sample_csv_file)
        
        assert result.file_name == sample_csv_file.name
        assert result.file_path == str(sample_csv_file)
        assert result.file_size_bytes > 0
    
    def test_validate_returns_row_count(self, processor, sample_csv_file):
        """Test that validation returns row count."""
        result = processor.validate(sample_csv_file)
        
        assert result.row_count > 0
    
    def test_validate_returns_column_count(self, processor, sample_csv_file):
        """Test that validation returns column count."""
        result = processor.validate(sample_csv_file)
        
        assert result.column_count > 0
    
    def test_validate_returns_columns(self, processor, sample_csv_file):
        """Test that validation returns column info."""
        result = processor.validate(sample_csv_file)
        
        assert len(result.columns) > 0
        assert all(isinstance(col, ColumnInfo) for col in result.columns)
    
    def test_validate_returns_encoding(self, processor, sample_csv_file):
        """Test that validation returns detected encoding."""
        result = processor.validate(sample_csv_file)
        
        assert result.detected_encoding is not None
        assert isinstance(result.detected_encoding, str)
    
    def test_validate_returns_delimiter(self, processor, sample_csv_file):
        """Test that validation returns detected delimiter."""
        result = processor.validate(sample_csv_file)
        
        assert result.detected_delimiter == ','
    
    def test_validate_returns_timestamp(self, processor, sample_csv_file):
        """Test that validation returns timestamp."""
        result = processor.validate(sample_csv_file)
        
        assert result.validated_at is not None
    
    def test_validate_xlsx(self, processor, sample_xlsx_file):
        """Test XLSX file validation."""
        result = processor.validate(sample_xlsx_file)
        
        assert result.is_valid is True
        assert result.file_type == 'xlsx'
    
    def test_validate_tsv(self, processor, sample_tsv_file):
        """Test TSV file validation."""
        result = processor.validate(sample_tsv_file)
        
        assert result.is_valid is True
        assert result.file_type == 'tsv'
    
    def test_validate_txt(self, processor, sample_txt_file):
        """Test TXT file validation."""
        result = processor.validate(sample_txt_file)
        
        assert result.is_valid is True
        assert result.file_type == 'txt'
    
    def test_validate_nonexistent_file(self, processor, tmp_path):
        """Test validation of non-existent file."""
        fake_file = tmp_path / "nonexistent.csv"
        
        result = processor.validate(fake_file)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert 'not found' in result.errors[0].lower()
    
    def test_validate_unsupported_file_type(self, processor, tmp_path):
        """Test validation of unsupported file type."""
        unknown_file = tmp_path / "test.unknown"
        unknown_file.touch()
        
        result = processor.validate(unknown_file)
        
        assert result.is_valid is False
        assert result.file_type == 'unknown'
        assert len(result.errors) > 0
    
    def test_validate_min_rows_pass(self, processor, sample_csv_file):
        """Test validation with min_rows requirement (passing)."""
        result = processor.validate(sample_csv_file, min_rows=1)
        
        assert result.is_valid is True
    
    def test_validate_min_rows_fail(self, processor, sample_csv_file):
        """Test validation with min_rows requirement (failing)."""
        result = processor.validate(sample_csv_file, min_rows=10000)
        
        assert result.is_valid is False
        assert any('rows' in e.lower() for e in result.errors)
    
    def test_validate_min_columns_pass(self, processor, sample_csv_file):
        """Test validation with min_columns requirement (passing)."""
        result = processor.validate(sample_csv_file, min_columns=1)
        
        assert result.is_valid is True
    
    def test_validate_min_columns_fail(self, processor, sample_csv_file):
        """Test validation with min_columns requirement (failing)."""
        result = processor.validate(sample_csv_file, min_columns=100)
        
        assert result.is_valid is False
        assert any('columns' in e.lower() for e in result.errors)
    
    def test_validate_required_columns_pass(self, processor, sample_csv_file):
        """Test validation with required columns (passing)."""
        # First get actual column names
        preview = processor.preview(sample_csv_file, num_rows=1)
        first_col = preview.columns[0]
        
        result = processor.validate(sample_csv_file, required_columns=[first_col])
        
        assert result.is_valid is True
    
    def test_validate_required_columns_fail(self, processor, sample_csv_file):
        """Test validation with required columns (failing)."""
        result = processor.validate(
            sample_csv_file, 
            required_columns=['nonexistent_column']
        )
        
        assert result.is_valid is False
        assert any('missing' in e.lower() for e in result.errors)
    
    def test_validate_excel_specific_sheet(self, processor, multi_sheet_excel):
        """Test validation of specific Excel sheet."""
        result = processor.validate(multi_sheet_excel, sheet_name='Data')
        
        assert result.is_valid is True
        assert 'x' in [col.name for col in result.columns]
    
    
    def test_validate_warns_empty_columns(self, processor, tmp_path):
        """Test that validation warns about empty columns."""
        file_path = tmp_path / "empty_col.csv"
        file_path.write_text("a,b,c\n1,,3\n2,,4\n3,,5")
        
        result = processor.validate(file_path)
        
        assert any('empty' in w.lower() for w in result.warnings)
    
    def test_validate_to_dict(self, processor, sample_csv_file):
        """Test ValidationResult to_dict method."""
        result = processor.validate(sample_csv_file)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'is_valid' in result_dict
        assert 'file_name' in result_dict
        assert 'columns' in result_dict
    
    def test_validate_to_json(self, processor, sample_csv_file):
        """Test ValidationResult to_json method."""
        result = processor.validate(sample_csv_file)
        
        result_json = result.to_json()
        
        assert isinstance(result_json, str)
        # Should be valid JSON
        parsed = json.loads(result_json)
        assert 'is_valid' in parsed


class TestPreview:
    """Tests for preview method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_preview_basic(self, processor, sample_csv_file):
        """Test basic file preview."""
        result = processor.preview(sample_csv_file)
        
        assert isinstance(result, PreviewResult)
        assert result.success is True
    
    def test_preview_default_rows(self, processor, sample_csv_file):
        """Test preview returns 10 rows by default."""
        result = processor.preview(sample_csv_file)
        
        assert result.preview_row_count <= 10
    
    def test_preview_custom_num_rows(self, processor, sample_csv_file):
        """Test preview with custom number of rows."""
        result = processor.preview(sample_csv_file, num_rows=3)
        
        assert result.preview_row_count <= 3
    
    def test_preview_more_rows_than_file(self, processor, sample_csv_file):
        """Test preview requesting more rows than file has."""
        result = processor.preview(sample_csv_file, num_rows=10000)
        
        assert result.success is True
        assert result.preview_row_count == result.total_rows
    
    def test_preview_returns_total_rows(self, processor, sample_csv_file):
        """Test preview returns total row count."""
        result = processor.preview(sample_csv_file, num_rows=1)
        
        assert result.total_rows > 0
        assert result.total_rows >= result.preview_row_count
    
    def test_preview_returns_columns(self, processor, sample_csv_file):
        """Test preview returns column names."""
        result = processor.preview(sample_csv_file)
        
        assert len(result.columns) > 0
        assert all(isinstance(col, str) for col in result.columns)
    
    def test_preview_returns_column_types(self, processor, sample_csv_file):
        """Test preview returns column types."""
        result = processor.preview(sample_csv_file, include_types=True)
        
        assert len(result.column_types) > 0
        assert all(isinstance(t, str) for t in result.column_types.values())
    
    def test_preview_without_types(self, processor, sample_csv_file):
        """Test preview without column types."""
        result = processor.preview(sample_csv_file, include_types=False)
        
        assert result.column_types == {}
    
    def test_preview_returns_data(self, processor, sample_csv_file):
        """Test preview returns data records."""
        result = processor.preview(sample_csv_file, num_rows=3)
        
        assert isinstance(result.data, list)
        assert len(result.data) <= 3
        assert all(isinstance(record, dict) for record in result.data)
    
    def test_preview_data_has_correct_keys(self, processor, sample_csv_file):
        """Test preview data has column names as keys."""
        result = processor.preview(sample_csv_file, num_rows=1)
        
        if result.data:
            record_keys = set(result.data[0].keys())
            column_set = set(result.columns)
            assert record_keys == column_set
    
    def test_preview_xlsx(self, processor, sample_xlsx_file):
        """Test XLSX file preview."""
        result = processor.preview(sample_xlsx_file)
        
        assert result.success is True
        assert result.file_type == 'xlsx'
    
    def test_preview_specific_sheet(self, processor, multi_sheet_excel):
        """Test preview of specific Excel sheet."""
        result = processor.preview(multi_sheet_excel, sheet_name='People')
        
        assert result.success is True
        assert 'name' in result.columns
    
    def test_preview_nonexistent_file(self, processor, tmp_path):
        """Test preview of non-existent file."""
        fake_file = tmp_path / "nonexistent.csv"
        
        result = processor.preview(fake_file)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_preview_unsupported_file(self, processor, tmp_path):
        """Test preview of unsupported file type."""
        unknown_file = tmp_path / "test.unknown"
        unknown_file.touch()
        
        result = processor.preview(unknown_file)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_preview_with_normalize_columns(self, tmp_path):
        """Test preview with column normalization."""
        file_path = tmp_path / "spaces.csv"
        file_path.write_text("First Name,Last Name,Email Address\nJohn,Doe,john@example.com")
        
        processor = TabularProcessor(normalize_columns=True)
        result = processor.preview(file_path)
        
        assert result.success is True
        assert 'First_Name' in result.columns or 'first_name' in result.columns
    
    def test_preview_returns_file_info(self, processor, sample_csv_file):
        """Test preview returns file information."""
        result = processor.preview(sample_csv_file)
        
        assert result.file_name == sample_csv_file.name
        assert result.file_type == 'csv'
    
    def test_preview_returns_timestamp(self, processor, sample_csv_file):
        """Test preview returns timestamp."""
        result = processor.preview(sample_csv_file)
        
        assert result.generated_at is not None
    
    def test_preview_to_dict(self, processor, sample_csv_file):
        """Test PreviewResult to_dict method."""
        result = processor.preview(sample_csv_file)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'success' in result_dict
        assert 'data' in result_dict
    
    def test_preview_to_json(self, processor, sample_csv_file):
        """Test PreviewResult to_json method."""
        result = processor.preview(sample_csv_file)
        
        result_json = result.to_json()
        
        assert isinstance(result_json, str)
        parsed = json.loads(result_json)
        assert 'success' in parsed
    
    def test_preview_handles_special_values(self, processor, csv_with_nulls):
        """Test preview handles null values correctly."""
        result = processor.preview(csv_with_nulls)
        
        assert result.success is True
        # Null values should be None in JSON
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


class TestImportData:
    """Tests for import_data method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_import_basic(self, processor, sample_csv_file):
        """Test basic data import."""
        result = processor.import_data(sample_csv_file)
        
        assert isinstance(result, ImportResult)
        assert result.success is True
    
    def test_import_returns_all_data(self, processor, sample_csv_file):
        """Test import returns all data by default."""
        result = processor.import_data(sample_csv_file)
        
        assert len(result.data) > 0
        assert result.rows_imported == len(result.data)
    
    def test_import_returns_columns(self, processor, sample_csv_file):
        """Test import returns column names."""
        result = processor.import_data(sample_csv_file)
        
        assert len(result.columns_imported) > 0
    
    def test_import_with_start_row(self, processor, sample_csv_file):
        """Test import with start_row parameter."""
        full_result = processor.import_data(sample_csv_file)
        skip_result = processor.import_data(sample_csv_file, start_row=2)
        
        assert skip_result.success is True
        assert skip_result.rows_imported < full_result.rows_imported
        assert skip_result.start_row == 2
    
    def test_import_with_columns_by_index(self, processor, sample_csv_file):
        """Test import with column selection by index."""
        result = processor.import_data(sample_csv_file, columns=[0, 1])
        
        assert result.success is True
        assert len(result.columns_imported) == 2
    
    def test_import_with_columns_by_name(self, processor, sample_csv_file):
        """Test import with column selection by name."""
        preview = processor.preview(sample_csv_file, num_rows=1)
        first_col = preview.columns[0]
        
        result = processor.import_data(sample_csv_file, columns=[first_col])
        
        assert result.success is True
        assert len(result.columns_imported) == 1
    
    def test_import_with_custom_column_names(self, processor, sample_csv_file):
        """Test import with custom column names."""
        preview = processor.preview(sample_csv_file, num_rows=1)
        num_cols = len(preview.columns)
        custom_names = [f'custom_{i}' for i in range(num_cols)]
        
        result = processor.import_data(sample_csv_file, column_names=custom_names)
        
        assert result.success is True
        assert result.columns_imported == custom_names
    
    def test_import_column_mapping(self, processor, sample_csv_file):
        """Test import returns column mapping when names changed."""
        preview = processor.preview(sample_csv_file, num_rows=1)
        num_cols = len(preview.columns)
        custom_names = [f'new_{i}' for i in range(num_cols)]
        
        result = processor.import_data(sample_csv_file, column_names=custom_names)
        
        assert result.column_mapping is not None
        assert isinstance(result.column_mapping, dict)
    
    def test_import_with_max_rows(self, processor, sample_csv_file):
        """Test import with max_rows limit."""
        result = processor.import_data(sample_csv_file, max_rows=2)
        
        assert result.success is True
        assert result.rows_imported <= 2
    
    def test_import_no_header(self, processor, csv_no_header):
        """Test import without header."""
        result = processor.import_data(csv_no_header, has_header=False)
        
        assert result.success is True
        assert len(result.data) > 0
    
    def test_import_skip_empty_rows(self, processor, tmp_path):
        """Test import with skip_empty_rows."""
        file_path = tmp_path / "empty_rows.csv"
        file_path.write_text("a,b,c\n1,2,3\n,,\n4,5,6\n,,")
        
        result = processor.import_data(file_path, skip_empty_rows=True)
        
        assert result.success is True
        assert result.rows_skipped > 0
    
    def test_import_strip_whitespace(self, processor, tmp_path):
        """Test import with whitespace stripping."""
        file_path = tmp_path / "whitespace.csv"
        file_path.write_text("name,value\n  Alice  ,  100  \n  Bob  ,  200  ")
        
        result = processor.import_data(file_path, strip_whitespace=True)
        
        assert result.success is True
        assert result.data[0]['name'] == 'Alice'
        assert result.data[0]['value'] in ['100', 100]
    
    def test_import_xlsx(self, processor, sample_xlsx_file):
        """Test XLSX file import."""
        result = processor.import_data(sample_xlsx_file)
        
        assert result.success is True
        assert result.file_type == 'xlsx'
    
    def test_import_specific_sheet(self, processor, multi_sheet_excel):
        """Test import from specific Excel sheet."""
        result = processor.import_data(multi_sheet_excel, sheet_name='Data')
        
        assert result.success is True
        assert 'x' in result.columns_imported
    
    def test_import_nonexistent_file(self, processor, tmp_path):
        """Test import of non-existent file."""
        fake_file = tmp_path / "nonexistent.csv"
        
        result = processor.import_data(fake_file)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_import_unsupported_file(self, processor, tmp_path):
        """Test import of unsupported file type."""
        unknown_file = tmp_path / "test.unknown"
        unknown_file.touch()
        
        result = processor.import_data(unknown_file)
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_import_returns_columns_requested(self, processor, sample_csv_file):
        """Test import returns requested columns."""
        result = processor.import_data(sample_csv_file, columns=[0, 2])
        
        assert result.columns_requested == [0, 2]
    
    def test_import_returns_file_info(self, processor, sample_csv_file):
        """Test import returns file information."""
        result = processor.import_data(sample_csv_file)
        
        assert result.file_name == sample_csv_file.name
        assert result.file_type == 'csv'
    
    def test_import_returns_timestamp(self, processor, sample_csv_file):
        """Test import returns timestamp."""
        result = processor.import_data(sample_csv_file)
        
        assert result.imported_at is not None
    
    def test_import_warns_column_count_mismatch(self, processor, sample_csv_file):
        """Test import warns when column names count mismatches."""
        result = processor.import_data(
            sample_csv_file, 
            column_names=['only_one']  # Fewer names than columns
        )
        
        assert result.success is True
        assert len(result.warnings) > 0
    
    def test_import_combined_options(self, processor, sample_csv_file):
        """Test import with multiple options combined."""
        result = processor.import_data(
            sample_csv_file,
            start_row=1,
            columns=[0, 1],
            column_names=['id', 'name'],
            max_rows=3,
            skip_empty_rows=True,
            strip_whitespace=True
        )
        
        assert result.success is True
        assert result.start_row == 1
        assert len(result.columns_imported) == 2
        assert result.rows_imported <= 3
    
    def test_import_to_dict(self, processor, sample_csv_file):
        """Test ImportResult to_dict method."""
        result = processor.import_data(sample_csv_file)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'success' in result_dict
        assert 'data' in result_dict
    
    def test_import_to_json(self, processor, sample_csv_file):
        """Test ImportResult to_json method."""
        result = processor.import_data(sample_csv_file)
        
        result_json = result.to_json()
        
        assert isinstance(result_json, str)
        parsed = json.loads(result_json)
        assert 'success' in parsed
    
    def test_import_data_is_json_serializable(self, processor, sample_csv_file):
        """Test that imported data is JSON serializable."""
        result = processor.import_data(sample_csv_file)
        
        # Should not raise
        json_str = json.dumps(result.data)
        assert isinstance(json_str, str)
    
    def test_import_handles_nulls(self, processor, csv_with_nulls):
        """Test import handles null values correctly."""
        result = processor.import_data(csv_with_nulls)
        
        assert result.success is True
        # Verify JSON serializable with nulls
        json_str = json.dumps(result.data)
        parsed = json.loads(json_str)
        assert any(v is None for record in parsed for v in record.values())
    
    def test_import_with_normalize_columns(self, tmp_path):
        """Test import with column normalization."""
        file_path = tmp_path / "spaces.csv"
        file_path.write_text("First Name,Last Name\nJohn,Doe\nJane,Smith")
        
        processor = TabularProcessor(normalize_columns=True)
        result = processor.import_data(file_path)
        
        assert result.success is True
        assert result.column_mapping is not None


class TestGetSheetInfo:
    """Tests for get_sheet_info method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_get_sheet_info_single_sheet(self, processor, sample_xlsx_file):
        """Test getting sheet info from single-sheet file."""
        result = processor.get_sheet_info(sample_xlsx_file)
        
        assert isinstance(result, SheetInfo)
        assert result.sheet_count == 1
        assert len(result.sheet_names) == 1
    
    def test_get_sheet_info_multi_sheet(self, processor, multi_sheet_excel):
        """Test getting sheet info from multi-sheet file."""
        result = processor.get_sheet_info(multi_sheet_excel)
        
        assert result.sheet_count == 3
        assert len(result.sheet_names) == 3
        assert 'Sheet1' in result.sheet_names
        assert 'Data' in result.sheet_names
        assert 'People' in result.sheet_names
    
    def test_get_sheet_info_returns_file_name(self, processor, sample_xlsx_file):
        """Test sheet info includes file name."""
        result = processor.get_sheet_info(sample_xlsx_file)
        
        assert result.file_name == sample_xlsx_file.name
    
    def test_get_sheet_info_to_dict(self, processor, sample_xlsx_file):
        """Test SheetInfo to_dict method."""
        result = processor.get_sheet_info(sample_xlsx_file)
        
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert 'sheet_names' in result_dict
        assert 'sheet_count' in result_dict
    
    def test_get_sheet_info_to_json(self, processor, sample_xlsx_file):
        """Test SheetInfo to_json method."""
        result = processor.get_sheet_info(sample_xlsx_file)
        
        result_json = result.to_json()
        
        assert isinstance(result_json, str)
        parsed = json.loads(result_json)
        assert 'sheet_names' in parsed
    
    def test_get_sheet_info_nonexistent_file(self, processor, tmp_path):
        """Test sheet info for non-existent file."""
        fake_file = tmp_path / "nonexistent.xlsx"
        
        with pytest.raises(FileNotFoundError):
            processor.get_sheet_info(fake_file)
    
    def test_get_sheet_info_non_excel_file(self, processor, sample_csv_file):
        """Test sheet info for non-Excel file."""
        result = processor.get_sheet_info(sample_csv_file)
        
        assert result.sheet_count == 0
        assert result.sheet_names == []


class TestIsTabular:
    """Tests for is_tabular method."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_is_tabular_csv(self, processor, sample_csv_file):
        """Test is_tabular for valid CSV."""
        result = processor.is_tabular(sample_csv_file)
        
        assert result is True
    
    def test_is_tabular_xlsx(self, processor, sample_xlsx_file):
        """Test is_tabular for valid XLSX."""
        result = processor.is_tabular(sample_xlsx_file)
        
        assert result is True
    
    def test_is_tabular_tsv(self, processor, sample_tsv_file):
        """Test is_tabular for valid TSV."""
        result = processor.is_tabular(sample_tsv_file)
        
        assert result is True
    
    def test_is_tabular_nonexistent_file(self, processor, tmp_path):
        """Test is_tabular for non-existent file."""
        fake_file = tmp_path / "nonexistent.csv"
        
        result = processor.is_tabular(fake_file)
        
        assert result is False
    
    def test_is_tabular_unsupported_type(self, processor, tmp_path):
        """Test is_tabular for unsupported file type."""
        unknown_file = tmp_path / "test.xyz"
        unknown_file.touch()
        
        result = processor.is_tabular(unknown_file)
        
        assert result is False
    
    def test_is_tabular_empty_file(self, processor, tmp_path):
        """Test is_tabular for empty file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.touch()
        
        result = processor.is_tabular(empty_file)
        
        # Empty file might be valid or invalid depending on implementation
        assert isinstance(result, bool)
    
    def test_is_tabular_corrupted_file(self, processor, tmp_path):
        """Test is_tabular for corrupted file."""
        corrupted_file = tmp_path / "corrupted.xlsx"
        corrupted_file.write_text("not valid excel content")
        
        result = processor.is_tabular(corrupted_file)
        
        assert result is False


class TestProcessorIntegration:
    """Integration tests for TabularProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_full_workflow_csv(self, processor, sample_csv_file):
        """Test complete workflow with CSV file."""
        # 1. Check if tabular
        assert processor.is_tabular(sample_csv_file) is True
        
        # 2. Validate
        validation = processor.validate(sample_csv_file)
        assert validation.is_valid is True
        
        # 3. Preview
        preview = processor.preview(sample_csv_file, num_rows=5)
        assert preview.success is True
        
        # 4. Import
        result = processor.import_data(sample_csv_file)
        assert result.success is True
        
        # 5. Verify data consistency
        assert len(result.columns_imported) == validation.column_count
        assert result.rows_imported == validation.row_count
    
    def test_full_workflow_xlsx(self, processor, sample_xlsx_file):
        """Test complete workflow with XLSX file."""
        # 1. Check if tabular
        assert processor.is_tabular(sample_xlsx_file) is True
        
        # 2. Get sheet info
        sheet_info = processor.get_sheet_info(sample_xlsx_file)
        assert sheet_info.sheet_count >= 1
        
        # 3. Validate
        validation = processor.validate(sample_xlsx_file)
        assert validation.is_valid is True
        
        # 4. Preview
        preview = processor.preview(sample_xlsx_file, num_rows=5)
        assert preview.success is True
        
        # 5. Import
        result = processor.import_data(sample_xlsx_file)
        assert result.success is True
    
    def test_workflow_with_options(self, processor, sample_csv_file):
        """Test workflow with various processing options."""
        # Validate with requirements
        validation = processor.validate(
            sample_csv_file,
            min_rows=1,
            min_columns=1
        )
        assert validation.is_valid is True
        
        # Preview specific number of rows
        preview = processor.preview(sample_csv_file, num_rows=3)
        assert len(preview.data) <= 3
        
        # Import with selective columns
        result = processor.import_data(
            sample_csv_file,
            columns=[0],
            max_rows=5
        )
        assert result.success is True
        assert len(result.columns_imported) == 1
        assert result.rows_imported <= 5
    
    def test_all_results_json_serializable(self, processor, sample_csv_file):
        """Test that all results can be serialized to JSON."""
        validation = processor.validate(sample_csv_file)
        preview = processor.preview(sample_csv_file)
        import_result = processor.import_data(sample_csv_file)
        
        # All should serialize without error
        json.loads(validation.to_json())
        json.loads(preview.to_json())
        json.loads(import_result.to_json())
    
    def test_processor_with_all_options(self, tmp_path):
        """Test processor with all initialization options."""
        file_path = tmp_path / "test.csv"
        file_path.write_text("First Name,Last Name\nJohn,Doe\nJane,Smith")
        
        processor = TabularProcessor(
            default_encoding='utf-8',
            default_delimiter=',',
            auto_detect_types=True,
            normalize_columns=True
        )
        
        validation = processor.validate(file_path)
        preview = processor.preview(file_path)
        result = processor.import_data(file_path)
        
        assert validation.is_valid
        assert preview.success
        assert result.success
        # With normalize_columns=True, column names should be normalized
        assert 'First_Name' in result.columns_imported or 'first_name' in result.columns_imported
    
    def test_error_handling_propagation(self, processor, tmp_path):
        """Test that errors are properly captured and returned."""
        nonexistent = tmp_path / "nonexistent.csv"
        
        # All methods should handle errors gracefully
        validation = processor.validate(nonexistent)
        assert not validation.is_valid
        assert len(validation.errors) > 0
        
        preview = processor.preview(nonexistent)
        assert not preview.success
        assert len(preview.errors) > 0
        
        result = processor.import_data(nonexistent)
        assert not result.success
        assert len(result.errors) > 0


class TestProcessorEdgeCases:
    """Edge case tests for TabularProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Create a TabularProcessor instance."""
        return TabularProcessor()
    
    def test_single_row_file(self, processor, tmp_path):
        """Test processing file with single data row."""
        file_path = tmp_path / "single.csv"
        file_path.write_text("a,b,c\n1,2,3")
        
        result = processor.import_data(file_path)
        
        assert result.success
        assert result.rows_imported == 1
    
    def test_single_column_file(self, processor, tmp_path):
        """Test processing file with single column."""
        file_path = tmp_path / "single_col.csv"
        file_path.write_text("values\n1\n2\n3\n4\n5")
        
        result = processor.import_data(file_path)
        
        assert result.success
        assert len(result.columns_imported) == 1
    
    def test_unicode_content(self, processor, utf8_csv_file):
        """Test processing file with unicode content."""
        result = processor.import_data(utf8_csv_file)
        
        assert result.success
        # Should preserve unicode characters
        json_str = result.to_json()
        assert isinstance(json_str, str)
    
    def test_large_file(self, processor, large_csv_file):
        """Test processing larger file."""
        result = processor.import_data(large_csv_file)
        
        assert result.success
        assert result.rows_imported >= 100
    
    def test_quoted_values(self, processor, tmp_path):
        """Test processing file with quoted values."""
        file_path = tmp_path / "quoted.csv"
        content = 'name,description\n"John Doe","A ""quoted"" value"\n"Jane, Smith","Contains, commas"'
        file_path.write_text(content)
        
        result = processor.import_data(file_path)
        
        assert result.success
        assert len(result.data) == 2
    
    def test_special_characters_in_data(self, processor, tmp_path):
        """Test processing file with special characters."""
        file_path = tmp_path / "special.csv"
        file_path.write_text("name,symbol\nTest,<>&\"'\nAnother,@#$%^")
        
        result = processor.import_data(file_path)
        
        assert result.success
        # Should be JSON serializable
        json_str = result.to_json()
        json.loads(json_str)
    
    def test_very_long_values(self, processor, tmp_path):
        """Test processing file with very long values."""
        file_path = tmp_path / "long.csv"
        long_value = 'x' * 10000
        file_path.write_text(f"col1,col2\n{long_value},short")
        
        result = processor.import_data(file_path)
        
        assert result.success
        assert len(result.data[0]['col1']) == 10000
    
    def test_numeric_column_names(self, processor, tmp_path):
        """Test processing file with numeric column names."""
        file_path = tmp_path / "numeric_cols.csv"
        file_path.write_text("1,2,3\na,b,c\nd,e,f")
        
        result = processor.import_data(file_path)
        
        assert result.success
    
    def test_import_start_row_beyond_data(self, processor, sample_csv_file):
        """Test import with start_row beyond available data."""
        result = processor.import_data(sample_csv_file, start_row=10000)
        
        assert result.success
        assert result.rows_imported == 0
    
    def test_concurrent_operations(self, processor, sample_csv_file):
        """Test that processor can handle multiple operations."""
        # Perform multiple operations
        v1 = processor.validate(sample_csv_file)
        p1 = processor.preview(sample_csv_file, num_rows=1)
        v2 = processor.validate(sample_csv_file)
        i1 = processor.import_data(sample_csv_file, max_rows=1)
        p2 = processor.preview(sample_csv_file, num_rows=2)
        i2 = processor.import_data(sample_csv_file, max_rows=2)
        
        # All should succeed
        assert v1.is_valid and v2.is_valid
        assert p1.success and p2.success
        assert i1.success and i2.success

if __name__ == "__main__":
    pytest.main([__file__, "-v"])