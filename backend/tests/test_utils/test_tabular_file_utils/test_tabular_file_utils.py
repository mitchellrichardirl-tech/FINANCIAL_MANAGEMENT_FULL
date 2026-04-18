import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date
import tempfile
import os

from src.utils.tabular_files.tabular_file_utils import (
    detect_file_type,
    detect_encoding,
    detect_delimiter,
    get_file_size,
    infer_column_type,
    sanitize_for_json,
    dataframe_to_json_records,
    normalize_column_names,
    EXTENSION_MAP,
    EXCEL_TYPES,
    TEXT_TYPES
)
from src.models.files import FileType, DataType


class TestDetectFileType:
    """Tests for detect_file_type function."""
    
    def test_detect_csv(self, sample_csv_file):
        """Test detection of CSV files."""
        result = detect_file_type(sample_csv_file)
        assert result == FileType.CSV
    
    def test_detect_tsv(self, sample_tsv_file):
        """Test detection of TSV files."""
        result = detect_file_type(sample_tsv_file)
        assert result == FileType.TSV
    
    def test_detect_txt(self, sample_txt_file):
        """Test detection of TXT files."""
        result = detect_file_type(sample_txt_file)
        assert result == FileType.TXT
    
    def test_detect_xlsx(self, sample_xlsx_file):
        """Test detection of XLSX files."""
        result = detect_file_type(sample_xlsx_file)
        assert result == FileType.XLSX
    
    def test_detect_xls(self, sample_xls_file):
        """Test detection of XLS files."""
        result = detect_file_type(sample_xls_file)
        assert result == FileType.XLS
    
    def test_detect_unknown_extension(self, tmp_path):
        """Test detection of unknown file types."""
        unknown_file = tmp_path / "test.unknown"
        unknown_file.touch()
        result = detect_file_type(unknown_file)
        assert result == FileType.UNKNOWN
    
    def test_detect_no_extension(self, tmp_path):
        """Test detection of files without extension."""
        no_ext_file = tmp_path / "noextension"
        no_ext_file.touch()
        result = detect_file_type(no_ext_file)
        assert result == FileType.UNKNOWN
    
    def test_detect_case_insensitive(self, tmp_path):
        """Test that file type detection is case-insensitive."""
        upper_csv = tmp_path / "test.CSV"
        upper_csv.touch()
        result = detect_file_type(upper_csv)
        assert result == FileType.CSV
    
    def test_detect_from_string_path(self, sample_csv_file):
        """Test detection when path is provided as string."""
        result = detect_file_type(str(sample_csv_file))
        assert result == FileType.CSV
    
    def test_detect_from_path_object(self, sample_csv_file):
        """Test detection when path is provided as Path object."""
        result = detect_file_type(Path(sample_csv_file))
        assert result == FileType.CSV
    
    @pytest.mark.parametrize("extension,expected_type", [
        ('.csv', FileType.CSV),
        ('.tsv', FileType.TSV),
        ('.txt', FileType.TXT),
        ('.xls', FileType.XLS),
        ('.xlsx', FileType.XLSX),
        ('.xlsm', FileType.XLSM),
        ('.xlsb', FileType.XLSB),
        ('.ods', FileType.ODS),
        ('.parquet', FileType.PARQUET),
        ('.json', FileType.JSON),
    ])
    def test_extension_mapping(self, tmp_path, extension, expected_type):
        """Test all supported file extensions."""
        test_file = tmp_path / f"test{extension}"
        test_file.touch()
        result = detect_file_type(test_file)
        assert result == expected_type


class TestDetectEncoding:
    """Tests for detect_encoding function."""
    
    def test_detect_utf8(self, utf8_csv_file):
        """Test detection of UTF-8 encoding."""
        result = detect_encoding(utf8_csv_file)
        assert result.lower() in ['utf-8', 'utf8', 'ascii']
    
    def test_detect_latin1(self, latin1_csv_file):
        """Test detection of Latin-1 encoding."""
        result = detect_encoding(latin1_csv_file)
        # chardet might detect as ISO-8859-1, Windows-1252, or similar
        assert result.lower() in ['iso-8859-1', 'latin-1', 'windows-1252', 'cp1252']
    
    def test_detect_ascii(self, sample_csv_file):
        """Test detection of ASCII/UTF-8 encoding."""
        result = detect_encoding(sample_csv_file)
        assert result.lower() in ['ascii', 'utf-8', 'utf8']
    
    def test_custom_sample_size(self, utf8_csv_file):
        """Test encoding detection with custom sample size."""
        result = detect_encoding(utf8_csv_file, sample_size=1000)
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_small_sample_size(self, sample_csv_file):
        """Test encoding detection with very small sample size."""
        result = detect_encoding(sample_csv_file, sample_size=100)
        assert isinstance(result, str)
    
    def test_empty_file_fallback(self, empty_csv_file):
        """Test that empty files fallback to utf-8."""
        result = detect_encoding(empty_csv_file)
        assert result == 'utf-8'
    
    def test_binary_file_fallback(self, tmp_path):
        """Test encoding detection on binary file."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(bytes(range(256)))
        result = detect_encoding(binary_file)
        assert isinstance(result, str)  # Should return some encoding
    
    def test_encoding_string_path(self, utf8_csv_file):
        """Test encoding detection with string path."""
        result = detect_encoding(str(utf8_csv_file))
        assert isinstance(result, str)
    
    def test_encoding_path_object(self, utf8_csv_file):
        """Test encoding detection with Path object."""
        result = detect_encoding(Path(utf8_csv_file))
        assert isinstance(result, str)


class TestDetectDelimiter:
    """Tests for detect_delimiter function."""
    
    def test_detect_comma_delimiter(self, sample_csv_file):
        """Test detection of comma delimiter."""
        result = detect_delimiter(sample_csv_file)
        assert result == ','
    
    def test_detect_tab_delimiter(self, sample_tsv_file):
        """Test detection of tab delimiter."""
        result = detect_delimiter(sample_tsv_file)
        assert result == '\t'
    
    def test_detect_pipe_delimiter(self, sample_txt_file):
        """Test detection of pipe delimiter."""
        result = detect_delimiter(sample_txt_file)
        assert result == '|'
    
    def test_detect_semicolon_delimiter(self, tmp_path):
        """Test detection of semicolon delimiter."""
        file_path = tmp_path / "semicolon.csv"
        content = "name;age;city\nJohn;30;NYC\nJane;25;LA"
        file_path.write_text(content)
        
        result = detect_delimiter(file_path)
        assert result == ';'
    
    def test_custom_encoding(self, sample_csv_file):
        """Test delimiter detection with custom encoding."""
        result = detect_delimiter(sample_csv_file, encoding='utf-8')
        assert result == ','
    
    def test_custom_sample_lines(self, sample_csv_file):
        """Test delimiter detection with custom sample lines."""
        result = detect_delimiter(sample_csv_file, sample_lines=5)
        assert result == ','
    
    def test_fallback_to_comma(self, tmp_path):
        """Test fallback to comma for ambiguous files."""
        file_path = tmp_path / "ambiguous.txt"
        content = "no clear delimiter here\njust some text\nnothing special"
        file_path.write_text(content)
        
        result = detect_delimiter(file_path)
        assert result == ','  # Should fallback to comma
    
    def test_empty_file_fallback(self, empty_csv_file):
        """Test delimiter detection on empty file."""
        result = detect_delimiter(empty_csv_file)
        assert result == ','  # Should fallback to comma


class TestGetFileSize:
    """Tests for get_file_size function."""
    
    def test_get_size_csv(self, sample_csv_file):
        """Test getting size of CSV file."""
        result = get_file_size(sample_csv_file)
        assert result > 0
        assert isinstance(result, int)
    
    def test_get_size_empty_file(self, empty_csv_file):
        """Test getting size of empty file."""
        result = get_file_size(empty_csv_file)
        assert result == 0
    
    def test_get_size_large_file(self, tmp_path):
        """Test getting size of larger file."""
        large_file = tmp_path / "large.csv"
        content = "col1,col2,col3\n" * 1000
        large_file.write_text(content)
        
        result = get_file_size(large_file)
        expected_size = len(content.encode('utf-8'))
        assert result == expected_size
    
    def test_get_size_string_path(self, sample_csv_file):
        """Test getting size with string path."""
        result = get_file_size(str(sample_csv_file))
        assert result > 0
    
    def test_get_size_path_object(self, sample_csv_file):
        """Test getting size with Path object."""
        result = get_file_size(Path(sample_csv_file))
        assert result > 0
    
    def test_get_size_excel(self, sample_xlsx_file):
        """Test getting size of Excel file."""
        result = get_file_size(sample_xlsx_file)
        assert result > 0


class TestInferColumnType:
    """Tests for infer_column_type function."""
    
    def test_infer_integer_type(self, sample_series_integer):
        """Test inference of integer type."""
        result = infer_column_type(sample_series_integer)
        assert result == DataType.INTEGER.value
    
    def test_infer_float_type(self, sample_series_float):
        """Test inference of float type."""
        result = infer_column_type(sample_series_float)
        assert result == DataType.FLOAT.value
    
    def test_infer_string_type(self, sample_series_string):
        """Test inference of string type."""
        result = infer_column_type(sample_series_string)
        assert result == DataType.STRING.value
    
    def test_infer_boolean_type(self, sample_series_boolean):
        """Test inference of boolean type."""
        result = infer_column_type(sample_series_boolean)
        assert result == DataType.BOOLEAN.value
    
    def test_infer_datetime_type(self, sample_series_datetime):
        """Test inference of datetime type."""
        result = infer_column_type(sample_series_datetime)
        assert result == DataType.DATETIME.value
    
    def test_infer_date_type(self, sample_series_date_strings):
        """Test inference of date type from string dates."""
        result = infer_column_type(sample_series_date_strings)
        # Should detect as date or string depending on parsing
        assert result in [DataType.DATE.value, DataType.STRING.value]
    
    def test_infer_mixed_type(self, sample_series_mixed):
        """Test inference of mixed string/number type."""
        result = infer_column_type(sample_series_mixed)
        assert result == DataType.STRING.value
    
    def test_infer_all_null(self):
        """Test inference of all-null column."""
        series = pd.Series([None, None, None, None])
        result = infer_column_type(series)
        assert result == DataType.STRING.value
    
    def test_infer_empty_series(self):
        """Test inference of empty series."""
        series = pd.Series([], dtype=object)
        result = infer_column_type(series)
        assert result == DataType.STRING.value
    
    def test_infer_numpy_integer(self):
        """Test inference of numpy integer types."""
        series = pd.Series(np.array([1, 2, 3, 4, 5], dtype=np.int32))
        result = infer_column_type(series)
        assert result == DataType.INTEGER.value
    
    def test_infer_numpy_float(self):
        """Test inference of numpy float types."""
        series = pd.Series(np.array([1.1, 2.2, 3.3], dtype=np.float64))
        result = infer_column_type(series)
        assert result == DataType.FLOAT.value
    
    def test_infer_with_nulls(self):
        """Test inference with null values present."""
        series = pd.Series([1, 2, None, 4, 5])
        result = infer_column_type(series)
        assert result in [DataType.INTEGER.value, DataType.FLOAT.value]


class TestSanitizeForJson:
    """Tests for sanitize_for_json function."""
    
    def test_sanitize_none(self):
        """Test sanitization of None values."""
        result = sanitize_for_json(None)
        assert result is None
    
    def test_sanitize_pd_na(self):
        """Test sanitization of pandas NA values."""
        result = sanitize_for_json(pd.NA)
        assert result is None
    
    def test_sanitize_numpy_nan(self):
        """Test sanitization of numpy NaN."""
        result = sanitize_for_json(np.nan)
        assert result is None
    
    def test_sanitize_numpy_integer(self):
        """Test sanitization of numpy integers."""
        result = sanitize_for_json(np.int64(42))
        assert result == 42
        assert isinstance(result, int)
    
    def test_sanitize_numpy_float(self):
        """Test sanitization of numpy floats."""
        result = sanitize_for_json(np.float64(3.14))
        assert result == 3.14
        assert isinstance(result, float)
    
    def test_sanitize_numpy_infinity(self):
        """Test sanitization of numpy infinity."""
        result = sanitize_for_json(np.inf)
        assert result is None
    
    def test_sanitize_numpy_negative_infinity(self):
        """Test sanitization of numpy negative infinity."""
        result = sanitize_for_json(-np.inf)
        assert result is None
    
    def test_sanitize_numpy_bool(self):
        """Test sanitization of numpy boolean."""
        result = sanitize_for_json(np.bool_(True))
        assert result is True
        assert isinstance(result, bool)
    
    def test_sanitize_datetime(self):
        """Test sanitization of datetime objects."""
        dt = datetime(2023, 1, 15, 10, 30, 45)
        result = sanitize_for_json(dt)
        assert result == '2023-01-15T10:30:45'
        assert isinstance(result, str)
    
    def test_sanitize_date(self):
        """Test sanitization of date objects."""
        d = date(2023, 1, 15)
        result = sanitize_for_json(d)
        assert result == '2023-01-15'
        assert isinstance(result, str)
    
    def test_sanitize_numpy_array(self):
        """Test sanitization of numpy arrays."""
        arr = np.array([1, 2, 3])
        result = sanitize_for_json(arr)
        assert result == [1, 2, 3]
        assert isinstance(result, list)
    
    def test_sanitize_bytes(self):
        """Test sanitization of bytes."""
        b = b'hello'
        result = sanitize_for_json(b)
        assert result == 'hello'
        assert isinstance(result, str)
    
    def test_sanitize_string(self):
        """Test that regular strings pass through."""
        result = sanitize_for_json("hello")
        assert result == "hello"
    
    def test_sanitize_integer(self):
        """Test that regular integers pass through."""
        result = sanitize_for_json(42)
        assert result == 42
    
    def test_sanitize_float(self):
        """Test that regular floats pass through."""
        result = sanitize_for_json(3.14)
        assert result == 3.14
    
    def test_sanitize_boolean(self):
        """Test that regular booleans pass through."""
        result = sanitize_for_json(True)
        assert result is True
    
    def test_sanitize_list(self):
        """Test that lists pass through."""
        result = sanitize_for_json([1, 2, 3])
        assert result == [1, 2, 3]
    
    def test_sanitize_dict(self):
        """Test that dictionaries pass through."""
        result = sanitize_for_json({'key': 'value'})
        assert result == {'key': 'value'}
    
    def test_sanitize_complex_object(self):
        """Test sanitization of complex objects."""
        class CustomObject:
            def __str__(self):
                return "custom"
        
        obj = CustomObject()
        result = sanitize_for_json(obj)
        assert result == "custom"


class TestDataframeToJsonRecords:
    """Tests for dataframe_to_json_records function."""
    
    def test_convert_simple_dataframe(self):
        """Test conversion of simple DataFrame."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie']
        })
        
        result = dataframe_to_json_records(df)
        
        assert len(result) == 3
        assert result[0] == {'id': 1, 'name': 'Alice'}
        assert result[1] == {'id': 2, 'name': 'Bob'}
        assert result[2] == {'id': 3, 'name': 'Charlie'}
    
    def test_convert_dataframe_with_nulls(self):
        """Test conversion with null values."""
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'value': [10, None, 30]
        })
        
        result = dataframe_to_json_records(df)
        
        assert result[0] == {'id': 1, 'value': 10}
        assert result[1] == {'id': 2, 'value': None}
        assert result[2] == {'id': 3, 'value': 30}
    
    def test_convert_dataframe_mixed_types(self, sample_dataframe):
        """Test conversion with mixed data types."""
        result = dataframe_to_json_records(sample_dataframe)
        
        assert len(result) == 5
        assert isinstance(result[0]['int_col'], int)
        assert isinstance(result[0]['float_col'], float)
        assert isinstance(result[0]['str_col'], str)
        assert isinstance(result[0]['bool_col'], bool)
        assert isinstance(result[0]['date_col'], str)  # Should be ISO format
    
    def test_convert_empty_dataframe(self):
        """Test conversion of empty DataFrame."""
        df = pd.DataFrame()
        result = dataframe_to_json_records(df)
        assert result == []
    
    def test_convert_dataframe_with_datetime(self):
        """Test conversion with datetime columns."""
        df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=3),
            'value': [1, 2, 3]
        })
        
        result = dataframe_to_json_records(df)
        
        assert len(result) == 3
        assert isinstance(result[0]['date'], str)
        assert 'T' in result[0]['date']  # ISO format
    
    def test_convert_dataframe_with_numpy_types(self):
        """Test conversion with numpy data types."""
        df = pd.DataFrame({
            'int': np.array([1, 2, 3], dtype=np.int64),
            'float': np.array([1.1, 2.2, 3.3], dtype=np.float64),
            'bool': np.array([True, False, True], dtype=np.bool_)
        })
        
        result = dataframe_to_json_records(df)
        
        assert isinstance(result[0]['int'], int)
        assert isinstance(result[0]['float'], float)
        assert isinstance(result[0]['bool'], bool)
    
    def test_convert_dataframe_special_column_names(self):
        """Test conversion with special column names."""
        df = pd.DataFrame({
            'column with spaces': [1, 2],
            'column-with-dashes': [3, 4],
            'column.with.dots': [5, 6]
        })
        
        result = dataframe_to_json_records(df)
        
        assert 'column with spaces' in result[0]
        assert 'column-with-dashes' in result[0]
        assert 'column.with.dots' in result[0]
    
    def test_convert_single_row(self):
        """Test conversion of single-row DataFrame."""
        df = pd.DataFrame({'a': [1], 'b': [2]})
        result = dataframe_to_json_records(df)
        
        assert len(result) == 1
        assert result[0] == {'a': 1, 'b': 2}


class TestNormalizeColumnNames:
    """Tests for normalize_column_names function."""
    
    def test_normalize_simple_names(self):
        """Test normalization of simple column names."""
        columns = ['name', 'age', 'city']
        result = normalize_column_names(columns)
        assert result == ['name', 'age', 'city']
    
    def test_normalize_names_with_spaces(self):
        """Test normalization of names with spaces."""
        columns = ['first name', 'last name', 'email address']
        result = normalize_column_names(columns)
        assert result == ['first_name', 'last_name', 'email_address']
    
    def test_normalize_names_with_special_chars(self):
        """Test normalization of names with special characters."""
        columns = ['name@', 'age#', 'city$']
        result = normalize_column_names(columns)
        assert result == ['name_', 'age_', 'city_']
    
    def test_normalize_names_with_hyphens(self):
        """Test normalization of names with hyphens."""
        columns = ['first-name', 'last-name', 'email-address']
        result = normalize_column_names(columns)
        assert result == ['first_name', 'last_name', 'email_address']
    
    def test_normalize_names_starting_with_number(self):
        """Test normalization of names starting with numbers."""
        columns = ['1name', '2age', '3city']
        result = normalize_column_names(columns)
        assert result == ['col_1name', 'col_2age', 'col_3city']
    
    def test_normalize_empty_names(self):
        """Test normalization of empty/whitespace names."""
        columns = ['', '  ', '\t']
        result = normalize_column_names(columns)
        assert result == ['unnamed', 'unnamed_1', 'unnamed_2']
    
    def test_normalize_duplicate_names(self):
        """Test normalization of duplicate column names."""
        columns = ['name', 'name', 'name']
        result = normalize_column_names(columns)
        assert result == ['name', 'name_1', 'name_2']
    
    def test_normalize_mixed_duplicates(self):
        """Test normalization with duplicates and special characters."""
        columns = ['First Name', 'first-name', 'first_name']
        result = normalize_column_names(columns)
        # After normalization, all should be 'first_name' variants
        assert len(result) == 3
        assert result[0] == 'first_name'
        assert result[1] in ['first_name_1', 'first_name']
    
    def test_normalize_numeric_columns(self):
        """Test normalization of purely numeric column names."""
        columns = [1, 2, 3]
        result = normalize_column_names(columns)
        assert result == ['col_1', 'col_2', 'col_3']
    
    def test_normalize_mixed_types(self):
        """Test normalization with mixed column name types."""
        columns = ['name', 123, 'age', 456.78]
        result = normalize_column_names(columns)
        assert result[0] == 'name'
        assert result[1] == 'col_123'
        assert result[2] == 'age'
        assert 'col_456' in result[3]
    
    def test_normalize_unicode_characters(self):
        """Test normalization of unicode characters."""
        columns = ['名前', 'возраст', 'città']
        result = normalize_column_names(columns)
        # Unicode letters should be preserved
        assert len(result) == 3
        assert all(isinstance(col, str) for col in result)
    
    def test_normalize_multiple_spaces(self):
        """Test normalization of multiple consecutive spaces."""
        columns = ['first  name', 'last   name']
        result = normalize_column_names(columns)
        assert result == ['first_name', 'last_name']
    
    def test_normalize_trailing_whitespace(self):
        """Test normalization with trailing whitespace."""
        columns = ['  name  ', '  age  ']
        result = normalize_column_names(columns)
        assert result == ['name', 'age']
    
    def test_normalize_preserves_order(self):
        """Test that normalization preserves column order."""
        columns = ['z_col', 'a_col', 'm_col']
        result = normalize_column_names(columns)
        assert result == ['z_col', 'a_col', 'm_col']
    
    def test_normalize_long_names(self):
        """Test normalization of very long column names."""
        long_name = 'a' * 1000
        columns = [long_name]
        result = normalize_column_names(columns)
        assert result[0] == long_name  # Should preserve length
    
    def test_normalize_empty_list(self):
        """Test normalization of empty column list."""
        columns = []
        result = normalize_column_names(columns)
        assert result == []


class TestConstants:
    """Tests for module constants."""
    
    def test_extension_map_contains_all_types(self):
        """Test that EXTENSION_MAP contains all expected file types."""
        expected_extensions = [
            '.csv', '.tsv', '.txt', '.xls', '.xlsx',
            '.xlsm', '.xlsb', '.ods', '.parquet', '.json'
        ]
        
        for ext in expected_extensions:
            assert ext in EXTENSION_MAP
    
    def test_excel_types_set(self):
        """Test that EXCEL_TYPES contains correct file types."""
        expected_excel = {
            FileType.XLS, FileType.XLSX, FileType.XLSM,
            FileType.XLSB, FileType.ODS
        }
        assert EXCEL_TYPES == expected_excel
    
    def test_text_types_set(self):
        """Test that TEXT_TYPES contains correct file types."""
        expected_text = {FileType.CSV, FileType.TSV, FileType.TXT}
        assert TEXT_TYPES == expected_text
    
    def test_no_overlap_between_excel_and_text(self):
        """Test that EXCEL_TYPES and TEXT_TYPES don't overlap."""
        assert EXCEL_TYPES.isdisjoint(TEXT_TYPES)


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_very_large_sample_size_encoding(self, sample_csv_file):
        """Test encoding detection with sample size larger than file."""
        file_size = get_file_size(sample_csv_file)
        result = detect_encoding(sample_csv_file, sample_size=file_size * 10)
        assert isinstance(result, str)
    
    def test_zero_sample_size_encoding(self, sample_csv_file):
        """Test encoding detection with zero sample size."""
        result = detect_encoding(sample_csv_file, sample_size=0)
        assert result == 'utf-8'  # Should fallback
    
    def test_delimiter_detection_single_column(self, tmp_path):
        """Test delimiter detection on single-column file."""
        file_path = tmp_path / "single_col.csv"
        content = "column1\nvalue1\nvalue2\nvalue3"
        file_path.write_text(content)
        
        result = detect_delimiter(file_path)
        assert isinstance(result, str)
    
    def test_sanitize_nested_numpy_arrays(self):
        """Test sanitization of nested numpy arrays."""
        nested = np.array([[1, 2], [3, 4]])
        result = sanitize_for_json(nested)
        assert result == [[1, 2], [3, 4]]
    
    def test_dataframe_with_multiindex(self):
        """Test conversion of DataFrame with MultiIndex."""
        df = pd.DataFrame(
            {'value': [1, 2, 3]},
            index=pd.MultiIndex.from_tuples([('a', 1), ('a', 2), ('b', 1)])
        )
        
        result = dataframe_to_json_records(df)
        assert len(result) == 3
        assert 'value' in result[0]
    
    def test_normalize_only_special_characters(self):
        """Test normalization of columns with only special characters."""
        columns = ['!!!', '@@@', '###']
        result = normalize_column_names(columns)
        assert len(result) == 3
        assert all('_' in col or col == 'unnamed' for col in result)
    
    def test_infer_type_single_value(self):
        """Test type inference with single-value series."""
        series = pd.Series([42])
        result = infer_column_type(series)
        assert result == DataType.INTEGER.value
    
    def test_sanitize_pandas_timestamp(self):
        """Test sanitization of pandas Timestamp."""
        ts = pd.Timestamp('2023-01-15 10:30:00')
        result = sanitize_for_json(ts)
        assert isinstance(result, str)
        assert '2023-01-15' in result
    
    def test_normalize_very_long_duplicate_names(self):
        """Test normalization with many duplicates."""
        columns = ['name'] * 100
        result = normalize_column_names(columns)
        
        assert len(result) == 100
        assert result[0] == 'name'
        assert result[-1] == 'name_99'
        assert len(set(result)) == 100  # All unique


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_full_file_processing_workflow(self, sample_csv_file):
        """Test complete workflow of file processing."""
        # Detect file type
        file_type = detect_file_type(sample_csv_file)
        assert file_type == FileType.CSV
        
        # Detect encoding
        encoding = detect_encoding(sample_csv_file)
        assert isinstance(encoding, str)
        
        # Detect delimiter
        delimiter = detect_delimiter(sample_csv_file, encoding)
        assert delimiter == ','
        
        # Get file size
        size = get_file_size(sample_csv_file)
        assert size > 0
        
        # Read and process
        df = pd.read_csv(sample_csv_file, encoding=encoding, delimiter=delimiter)
        
        # Normalize columns
        normalized_cols = normalize_column_names(df.columns.tolist())
        df.columns = normalized_cols
        
        # Convert to JSON records
        records = dataframe_to_json_records(df)
        assert len(records) > 0
        assert isinstance(records[0], dict)
    
    def test_processing_with_type_inference(self, sample_csv_file):
        """Test processing with type inference."""
        df = pd.read_csv(sample_csv_file)
        
        column_types = {}
        for col in df.columns:
            column_types[col] = infer_column_type(df[col])
        
        assert len(column_types) == len(df.columns)
        assert all(isinstance(t, str) for t in column_types.values())
    
    def test_multi_format_detection(self, sample_csv_file, sample_xlsx_file, 
                                    sample_tsv_file, sample_txt_file):
        """Test detection across multiple file formats."""
        files_and_types = [
            (sample_csv_file, FileType.CSV),
            (sample_xlsx_file, FileType.XLSX),
            (sample_tsv_file, FileType.TSV),
            (sample_txt_file, FileType.TXT),
        ]
        
        for file_path, expected_type in files_and_types:
            detected_type = detect_file_type(file_path)
            assert detected_type == expected_type

if __name__ == "__main__":
    pytest.main([__file__, "-v"])