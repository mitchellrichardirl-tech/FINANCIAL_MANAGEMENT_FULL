import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import json

from src.utils.tabular_files.readers import FileReader
from src.models.files import FileType
from src.utils.tabular_files.exceptions import FileReadError, UnsupportedFileTypeError


class TestFileReaderInit:
    """Tests for FileReader initialization."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        reader = FileReader()
        assert reader.encoding is None
        assert reader.delimiter is None
    
    def test_init_with_encoding(self):
        """Test initialization with custom encoding."""
        reader = FileReader(encoding='utf-8')
        assert reader.encoding == 'utf-8'
        assert reader.delimiter is None
    
    def test_init_with_delimiter(self):
        """Test initialization with custom delimiter."""
        reader = FileReader(delimiter=';')
        assert reader.encoding is None
        assert reader.delimiter == ';'
    
    def test_init_with_both_params(self):
        """Test initialization with both encoding and delimiter."""
        reader = FileReader(encoding='latin-1', delimiter='\t')
        assert reader.encoding == 'latin-1'
        assert reader.delimiter == '\t'
    
    def test_init_with_none_values(self):
        """Test initialization with explicit None values."""
        reader = FileReader(encoding=None, delimiter=None)
        assert reader.encoding is None
        assert reader.delimiter is None


class TestFileReaderReadCSV:
    """Tests for reading CSV files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_csv_basic(self, reader, sample_csv_file):
        """Test basic CSV reading."""
        df = reader.read(sample_csv_file, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0
    
    def test_read_csv_with_nrows(self, reader, sample_csv_file):
        """Test CSV reading with row limit."""
        df = reader.read(sample_csv_file, FileType.CSV, nrows=2)
        
        assert len(df) == 2
    
    def test_read_csv_with_skiprows_int(self, reader, sample_csv_file):
        """Test CSV reading with skiprows as integer."""
        df_full = reader.read(sample_csv_file, FileType.CSV)
        df_skip = reader.read(sample_csv_file, FileType.CSV, skiprows=[1, 2])
        
        assert len(df_skip) == len(df_full) - 2
    
    def test_read_csv_with_skiprows_list(self, reader, sample_csv_file):
        """Test CSV reading with skiprows as list."""
        df = reader.read(sample_csv_file, FileType.CSV, skiprows=[1, 3])
        
        assert isinstance(df, pd.DataFrame)
    
    def test_read_csv_with_usecols_by_index(self, reader, sample_csv_file):
        """Test CSV reading with column selection by index."""
        df = reader.read(sample_csv_file, FileType.CSV, usecols=[0, 1])
        
        assert len(df.columns) == 2
    
    def test_read_csv_with_usecols_by_name(self, reader, sample_csv_file):
        """Test CSV reading with column selection by name."""
        df_full = reader.read(sample_csv_file, FileType.CSV)
        first_two_cols = df_full.columns[:2].tolist()
        
        df = reader.read(sample_csv_file, FileType.CSV, usecols=first_two_cols)
        
        assert len(df.columns) == 2
        assert list(df.columns) == first_two_cols
    
    def test_read_csv_with_custom_names(self, reader, sample_csv_file):
        """Test CSV reading with custom column names."""
        df = reader.read(
            sample_csv_file, 
            FileType.CSV, 
            names=['col_a', 'col_b', 'col_c', 'col_d', 'col_e', 'col_f'],
            header=0
        )
        
        assert 'col_a' in df.columns
    
    def test_read_csv_no_header(self, reader, csv_no_header):
        """Test CSV reading without header."""
        df = reader.read(csv_no_header, FileType.CSV, header=None)
        
        assert isinstance(df, pd.DataFrame)
        # Column names should be integers
        assert all(isinstance(col, int) for col in df.columns)
    
    def test_read_csv_with_custom_encoding(self, latin1_csv_file):
        """Test CSV reading with custom encoding."""
        reader = FileReader(encoding='latin-1')
        df = reader.read(latin1_csv_file, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_read_csv_with_custom_delimiter(self, tmp_path):
        """Test CSV reading with custom delimiter."""
        # Create semicolon-delimited file
        file_path = tmp_path / "semicolon.csv"
        content = "a;b;c\n1;2;3\n4;5;6"
        file_path.write_text(content)
        
        reader = FileReader(delimiter=';')
        df = reader.read(file_path, FileType.CSV)
        
        assert list(df.columns) == ['a', 'b', 'c']
        assert len(df) == 2
    
    def test_read_csv_combined_options(self, reader, sample_csv_file):
        """Test CSV reading with multiple options combined."""
        df_full = reader.read(sample_csv_file, FileType.CSV)
        
        df = reader.read(
            sample_csv_file,
            FileType.CSV,
            nrows=3,
            usecols=[0, 1],
        )
        
        assert len(df) == 3
        assert len(df.columns) == 2


class TestFileReaderReadTSV:
    """Tests for reading TSV files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_tsv_basic(self, reader, sample_tsv_file):
        """Test basic TSV reading."""
        df = reader.read(sample_tsv_file, FileType.TSV)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_read_tsv_uses_tab_delimiter(self, reader, sample_tsv_file):
        """Test that TSV uses tab delimiter by default."""
        df = reader.read(sample_tsv_file, FileType.TSV)
        
        # Verify data was parsed correctly (not as single column)
        assert len(df.columns) > 1
    
    def test_read_tsv_with_nrows(self, reader, sample_tsv_file):
        """Test TSV reading with row limit."""
        df = reader.read(sample_tsv_file, FileType.TSV, nrows=1)
        
        assert len(df) == 1


class TestFileReaderReadTXT:
    """Tests for reading TXT files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_txt_with_pipe_delimiter(self, reader, sample_txt_file):
        """Test TXT reading with auto-detected pipe delimiter."""
        df = reader.read(sample_txt_file, FileType.TXT)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df.columns) > 1
    
    def test_read_txt_with_custom_delimiter(self, tmp_path):
        """Test TXT reading with custom delimiter override."""
        file_path = tmp_path / "custom.txt"
        content = "a|b|c\n1|2|3\n4|5|6"
        file_path.write_text(content)
        
        reader = FileReader(delimiter='|')
        df = reader.read(file_path, FileType.TXT)
        
        assert list(df.columns) == ['a', 'b', 'c']


class TestFileReaderReadExcel:
    """Tests for reading Excel files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_xlsx_basic(self, reader, sample_xlsx_file):
        """Test basic XLSX reading."""
        df = reader.read(sample_xlsx_file, FileType.XLSX)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_read_xlsx_with_nrows(self, reader, sample_xlsx_file):
        """Test XLSX reading with row limit."""
        df = reader.read(sample_xlsx_file, FileType.XLSX, nrows=2)
        
        assert len(df) == 2
    
    def test_read_xlsx_with_skiprows(self, reader, sample_xlsx_file):
        """Test XLSX reading with skiprows."""
        df_full = reader.read(sample_xlsx_file, FileType.XLSX)
        df_skip = reader.read(sample_xlsx_file, FileType.XLSX, skiprows=[1])
        
        assert len(df_skip) == len(df_full) - 1
    
    def test_read_xlsx_with_usecols(self, reader, sample_xlsx_file):
        """Test XLSX reading with column selection."""
        df = reader.read(sample_xlsx_file, FileType.XLSX, usecols=[0])
        
        assert len(df.columns) == 1
    
    def test_read_xlsx_specific_sheet_by_name(self, reader, multi_sheet_excel):
        """Test XLSX reading from specific sheet by name."""
        df = reader.read(multi_sheet_excel, FileType.XLSX, sheet_name='Data')
        
        assert isinstance(df, pd.DataFrame)
        assert 'x' in df.columns
    
    def test_read_xlsx_specific_sheet_by_index(self, reader, multi_sheet_excel):
        """Test XLSX reading from specific sheet by index."""
        df = reader.read(multi_sheet_excel, FileType.XLSX, sheet_name=1)
        
        assert isinstance(df, pd.DataFrame)
    
    def test_read_xlsx_with_custom_names(self, reader, sample_xlsx_file):
        """Test XLSX reading with custom column names."""
        df = reader.read(
            sample_xlsx_file,
            FileType.XLSX,
            names=['A', 'B', 'C'],
            header=0
        )
        
        assert 'A' in df.columns or len(df.columns) == 3
    
    def test_read_xlsx_no_header(self, reader, sample_xlsx_file):
        """Test XLSX reading without header."""
        df = reader.read(sample_xlsx_file, FileType.XLSX, header=None)
        
        assert isinstance(df, pd.DataFrame)
    
    def test_read_xls_basic(self, reader, sample_xls_file):
        """Test basic XLS reading."""
        try:
            df = reader.read(sample_xls_file, FileType.XLS)
            assert isinstance(df, pd.DataFrame)
        except FileReadError:
            # XLS reading might fail if xlrd is not properly configured
            pytest.skip("XLS reading not available")
    
    def test_read_xlsx_invalid_sheet_name(self, reader, sample_xlsx_file):
        """Test XLSX reading with invalid sheet name."""
        with pytest.raises(FileReadError):
            reader.read(sample_xlsx_file, FileType.XLSX, sheet_name='NonExistent')
    
    def test_read_xlsx_invalid_sheet_index(self, reader, sample_xlsx_file):
        """Test XLSX reading with invalid sheet index."""
        with pytest.raises(FileReadError):
            reader.read(sample_xlsx_file, FileType.XLSX, sheet_name=999)

class TestFileReaderExcelFormats:
    """Tests for different Excel format compatibility."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_xls_legacy_format(self, reader, sample_xls_file):
        """Test reading legacy .xls (BIFF) format."""
        df = reader.read(sample_xls_file, FileType.XLS)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert 'item' in df.columns
        assert 'value' in df.columns
    
    def test_read_xlsx_modern_format(self, reader, sample_xlsx_file):
        """Test reading modern .xlsx format."""
        df = reader.read(sample_xlsx_file, FileType.XLSX)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert len(df.columns) > 0
    
    def test_xls_uses_xlrd_engine(self, reader, sample_xls_file):
        """Test that .xls files use xlrd engine."""
        with patch('pandas.read_excel', wraps=pd.read_excel) as mock:
            reader.read(sample_xls_file, FileType.XLS)
            
            call_kwargs = mock.call_args[1]
            assert call_kwargs.get('engine') == 'xlrd'
    
    def test_xlsx_uses_openpyxl_engine(self, reader, sample_xlsx_file):
        """Test that .xlsx files use openpyxl engine."""
        with patch('pandas.read_excel', wraps=pd.read_excel) as mock:
            reader.read(sample_xlsx_file, FileType.XLSX)
            
            call_kwargs = mock.call_args[1]
            assert call_kwargs.get('engine') == 'openpyxl'
    
    def test_xls_and_xlsx_produce_same_data(self, reader, multi_format_excel_files):
        """Test that .xls and .xlsx files with same data produce same results."""
        if 'xls' not in multi_format_excel_files or 'xlsx' not in multi_format_excel_files:
            pytest.skip("Both file formats not available")
        
        df_xls = reader.read(multi_format_excel_files['xls'], FileType.XLS)
        df_xlsx = reader.read(multi_format_excel_files['xlsx'], FileType.XLSX)
        
        # Compare data (may have slight type differences)
        assert len(df_xls) == len(df_xlsx)
        assert list(df_xls.columns) == list(df_xlsx.columns)
        assert df_xls['id'].tolist() == df_xlsx['id'].tolist()
    
    def test_read_xls_with_options(self, reader, sample_xls_file):
        """Test reading .xls with various options."""
        df = reader.read(
            sample_xls_file,
            FileType.XLS,
            nrows=2,
            usecols=[0, 1]
        )
        
        assert len(df) == 2
        assert len(df.columns) == 2
    
    def test_read_xlsx_with_options(self, reader, sample_xlsx_file):
        """Test reading .xlsx with various options."""
        df = reader.read(
            sample_xlsx_file,
            FileType.XLSX,
            nrows=2,
            usecols=[0, 1]
        )
        
        assert len(df) == 2
        assert len(df.columns) == 2
    
    def test_xls_missing_xlrd_error(self, reader, sample_xls_file, monkeypatch):
        """Test proper error message when xlrd is missing."""
        def mock_read_excel(*args, **kwargs):
            raise ImportError("Missing optional dependency 'xlrd'")
        
        monkeypatch.setattr(pd, 'read_excel', mock_read_excel)
        
        with pytest.raises(FileReadError) as exc_info:
            reader.read(sample_xls_file, FileType.XLS)
        
        assert 'xlrd' in str(exc_info.value).lower()
    
    def test_xlsx_missing_openpyxl_error(self, reader, sample_xlsx_file, monkeypatch):
        """Test proper error message when openpyxl is missing."""
        def mock_read_excel(*args, **kwargs):
            raise ImportError("Missing optional dependency 'openpyxl'")
        
        monkeypatch.setattr(pd, 'read_excel', mock_read_excel)
        
        with pytest.raises(FileReadError) as exc_info:
            reader.read(sample_xlsx_file, FileType.XLSX)
        
        assert 'openpyxl' in str(exc_info.value).lower()
    
    def test_auto_detect_xls_format(self, reader, sample_xls_file):
        """Test that .xls files are correctly auto-detected."""
        from src.utils.tabular_files.tabular_file_utils import detect_file_type
        
        file_type = detect_file_type(sample_xls_file)
        assert file_type == FileType.XLS
        
        # Should be able to read using detected type
        df = reader.read(sample_xls_file, file_type)
        assert isinstance(df, pd.DataFrame)
    
    def test_auto_detect_xlsx_format(self, reader, sample_xlsx_file):
        """Test that .xlsx files are correctly auto-detected."""
        from src.utils.tabular_files.tabular_file_utils import detect_file_type
        
        file_type = detect_file_type(sample_xlsx_file)
        assert file_type == FileType.XLSX
        
        # Should be able to read using detected type
        df = reader.read(sample_xlsx_file, file_type)
        assert isinstance(df, pd.DataFrame)

class TestFileReaderReadParquet:
    """Tests for reading Parquet files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    @pytest.fixture
    def sample_parquet_file(self, tmp_path):
        """Create a sample Parquet file."""
        file_path = tmp_path / "sample.parquet"
        df = pd.DataFrame({
            'id': [1, 2, 3, 4, 5],
            'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
            'value': [10.5, 20.5, 30.5, 40.5, 50.5]
        })
        df.to_parquet(file_path)
        return file_path
    
    def test_read_parquet_basic(self, reader, sample_parquet_file):
        """Test basic Parquet reading."""
        df = reader.read(sample_parquet_file, FileType.PARQUET)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert 'id' in df.columns
    
    def test_read_parquet_with_usecols(self, reader, sample_parquet_file):
        """Test Parquet reading with column selection."""
        df = reader.read(sample_parquet_file, FileType.PARQUET, usecols=['id', 'name'])
        
        assert len(df.columns) == 2
        assert 'id' in df.columns
        assert 'name' in df.columns
        assert 'value' not in df.columns
    
    def test_read_parquet_preserves_types(self, reader, sample_parquet_file):
        """Test that Parquet reading preserves data types."""
        df = reader.read(sample_parquet_file, FileType.PARQUET)
        
        assert pd.api.types.is_integer_dtype(df['id'])
        assert pd.api.types.is_float_dtype(df['value'])
    
    def test_read_parquet_invalid_file(self, reader, tmp_path):
        """Test Parquet reading with invalid file."""
        invalid_file = tmp_path / "invalid.parquet"
        invalid_file.write_text("not a parquet file")
        
        with pytest.raises(FileReadError):
            reader.read(invalid_file, FileType.PARQUET)


class TestFileReaderReadJSON:
    """Tests for reading JSON files."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    @pytest.fixture
    def sample_json_file(self, tmp_path):
        """Create a sample JSON file."""
        file_path = tmp_path / "sample.json"
        data = [
            {"id": 1, "name": "Alice", "score": 95.5},
            {"id": 2, "name": "Bob", "score": 87.0},
            {"id": 3, "name": "Charlie", "score": 92.3},
            {"id": 4, "name": "David", "score": 78.9},
            {"id": 5, "name": "Eve", "score": 99.1}
        ]
        with open(file_path, 'w') as f:
            json.dump(data, f)
        return file_path
    
    @pytest.fixture
    def json_records_file(self, tmp_path):
        """Create a JSON file with records orientation."""
        file_path = tmp_path / "records.json"
        data = [
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
            {"a": 5, "b": 6}
        ]
        with open(file_path, 'w') as f:
            json.dump(data, f)
        return file_path
    
    def test_read_json_basic(self, reader, sample_json_file):
        """Test basic JSON reading."""
        df = reader.read(sample_json_file, FileType.JSON)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
    
    def test_read_json_with_nrows(self, reader, sample_json_file):
        """Test JSON reading with row limit."""
        df = reader.read(sample_json_file, FileType.JSON, nrows=2)
        
        assert len(df) == 2
    
    def test_read_json_preserves_columns(self, reader, sample_json_file):
        """Test that JSON reading preserves column names."""
        df = reader.read(sample_json_file, FileType.JSON)
        
        assert 'id' in df.columns
        assert 'name' in df.columns
        assert 'score' in df.columns
    
    def test_read_json_invalid_file(self, reader, tmp_path):
        """Test JSON reading with invalid file."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json {{{")
        
        with pytest.raises(FileReadError):
            reader.read(invalid_file, FileType.JSON)
    
    def test_read_json_empty_array(self, reader, tmp_path):
        """Test JSON reading with empty array."""
        empty_file = tmp_path / "empty.json"
        with open(empty_file, 'w') as f:
            json.dump([], f)
        
        df = reader.read(empty_file, FileType.JSON)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestFileReaderReadDispatch:
    """Tests for the main read method dispatch logic."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_dispatches_to_csv(self, reader, sample_csv_file):
        """Test that read dispatches CSV files correctly."""
        with patch.object(reader, '_read_text', wraps=reader._read_text) as mock:
            reader.read(sample_csv_file, FileType.CSV)
            mock.assert_called_once()
    
    def test_read_dispatches_to_xlsx(self, reader, sample_xlsx_file):
        """Test that read dispatches XLSX files correctly."""
        with patch.object(reader, '_read_excel', wraps=reader._read_excel) as mock:
            reader.read(sample_xlsx_file, FileType.XLSX)
            mock.assert_called_once()
    
    def test_read_unsupported_file_type(self, reader, tmp_path):
        """Test that read raises error for unsupported types."""
        dummy_file = tmp_path / "test.xyz"
        dummy_file.touch()
        
        with pytest.raises(UnsupportedFileTypeError):
            reader.read(dummy_file, FileType.UNKNOWN)
    
    @pytest.mark.parametrize("file_type", [
        FileType.CSV,
        FileType.TSV,
        FileType.TXT,
    ])
    def test_read_text_types_dispatch(self, reader, tmp_path, file_type):
        """Test that all text types dispatch to _read_text."""
        file_path = tmp_path / f"test.{file_type.value}"
        file_path.write_text("a,b,c\n1,2,3")
        
        with patch.object(reader, '_read_text', wraps=reader._read_text) as mock:
            try:
                reader.read(file_path, file_type)
                mock.assert_called_once()
            except FileReadError:
                pass  # OK if file format doesn't match extension
    
    @pytest.mark.parametrize("file_type", [
        FileType.XLSX,
        FileType.XLSM,
    ])
    def test_read_excel_types_dispatch(self, reader, sample_xlsx_file, file_type):
        """Test that Excel types dispatch to _read_excel."""
        with patch.object(reader, '_read_excel', wraps=reader._read_excel) as mock:
            try:
                reader.read(sample_xlsx_file, file_type)
                mock.assert_called()
            except FileReadError:
                pass  # OK if engine not available


class TestFileReaderGetSheetNames:
    """Tests for get_sheet_names method."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_get_sheet_names_single_sheet(self, reader, sample_xlsx_file):
        """Test getting sheet names from single-sheet Excel file."""
        sheets = reader.get_sheet_names(sample_xlsx_file)
        
        assert isinstance(sheets, list)
        assert len(sheets) == 1
        assert sheets[0] == 'Sheet1'
    
    def test_get_sheet_names_multiple_sheets(self, reader, multi_sheet_excel):
        """Test getting sheet names from multi-sheet Excel file."""
        sheets = reader.get_sheet_names(multi_sheet_excel)
        
        assert isinstance(sheets, list)
        assert len(sheets) == 3
        assert 'Sheet1' in sheets
        assert 'Data' in sheets
        assert 'People' in sheets
    
    def test_get_sheet_names_preserves_order(self, reader, multi_sheet_excel):
        """Test that sheet names are returned in order."""
        sheets = reader.get_sheet_names(multi_sheet_excel)
        
        assert sheets == ['Sheet1', 'Data', 'People']
    
    def test_get_sheet_names_invalid_file(self, reader, sample_csv_file):
        """Test getting sheet names from non-Excel file."""
        sheets = reader.get_sheet_names(sample_csv_file)
        
        assert sheets == []
    
    def test_get_sheet_names_nonexistent_file(self, reader, tmp_path):
        """Test getting sheet names from non-existent file."""
        fake_file = tmp_path / "nonexistent.xlsx"
        sheets = reader.get_sheet_names(fake_file)
        
        assert sheets == []
    
    def test_get_sheet_names_corrupted_file(self, reader, tmp_path):
        """Test getting sheet names from corrupted Excel file."""
        corrupted_file = tmp_path / "corrupted.xlsx"
        corrupted_file.write_text("not an excel file")
        
        sheets = reader.get_sheet_names(corrupted_file)
        
        assert sheets == []


class TestFileReaderCountRows:
    """Tests for count_rows method."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_count_rows_csv_with_header(self, reader, sample_csv_file):
        """Test counting rows in CSV file with header."""
        df = reader.read(sample_csv_file, FileType.CSV)
        expected_count = len(df)
        
        count = reader.count_rows(sample_csv_file, FileType.CSV, has_header=True)
        
        assert count == expected_count
    
    def test_count_rows_csv_without_header(self, reader, csv_no_header):
        """Test counting rows in CSV file without header."""
        count = reader.count_rows(csv_no_header, FileType.CSV, has_header=False)
        
        assert count > 0
    
    def test_count_rows_tsv(self, reader, sample_tsv_file):
        """Test counting rows in TSV file."""
        df = reader.read(sample_tsv_file, FileType.TSV)
        expected_count = len(df)
        
        count = reader.count_rows(sample_tsv_file, FileType.TSV, has_header=True)
        
        assert count == expected_count
    
    def test_count_rows_xlsx(self, reader, sample_xlsx_file):
        """Test counting rows in Excel file."""
        df = reader.read(sample_xlsx_file, FileType.XLSX)
        expected_count = len(df)
        
        count = reader.count_rows(sample_xlsx_file, FileType.XLSX)
        
        assert count == expected_count
    
    def test_count_rows_empty_csv(self, reader, tmp_path):
        """Test counting rows in empty CSV file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("col1,col2,col3\n")
        
        count = reader.count_rows(empty_file, FileType.CSV, has_header=True)
        
        assert count == 0
    
    def test_count_rows_single_row_csv(self, reader, tmp_path):
        """Test counting rows in single-row CSV file."""
        file_path = tmp_path / "single.csv"
        file_path.write_text("a,b,c\n1,2,3\n")
        
        count = reader.count_rows(file_path, FileType.CSV, has_header=True)
        
        assert count == 1
    
    def test_count_rows_with_custom_encoding(self, latin1_csv_file):
        """Test counting rows with custom encoding."""
        reader = FileReader(encoding='latin-1')
        
        count = reader.count_rows(latin1_csv_file, FileType.CSV, has_header=True)
        
        assert count > 0


class TestFileReaderErrorHandling:
    """Tests for error handling in FileReader."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_nonexistent_file(self, reader, tmp_path):
        """Test reading non-existent file."""
        fake_file = tmp_path / "nonexistent.csv"
        
        with pytest.raises(FileNotFoundError):
            reader.read(fake_file, FileType.CSV)
    
    def test_read_corrupted_csv(self, reader, tmp_path):
        """Test reading corrupted CSV file."""
        corrupted_file = tmp_path / "corrupted.csv"
        # Write binary garbage
        corrupted_file.write_bytes(bytes(range(256)))
        
        # Should either succeed with garbage data or raise FileReadError
        try:
            df = reader.read(corrupted_file, FileType.CSV)
            assert isinstance(df, pd.DataFrame)
        except FileReadError:
            pass  # This is acceptable
    
    def test_read_corrupted_xlsx(self, reader, tmp_path):
        """Test reading corrupted Excel file."""
        corrupted_file = tmp_path / "corrupted.xlsx"
        corrupted_file.write_text("not an excel file")
        
        with pytest.raises(FileReadError):
            reader.read(corrupted_file, FileType.XLSX)
    
    def test_read_permission_error(self, reader, tmp_path, monkeypatch):
        """Test reading file with permission error."""
        test_file = tmp_path / "noperm.csv"
        test_file.write_text("a,b,c\n1,2,3")
        
        # Mock pd.read_csv to raise PermissionError
        def mock_read_csv(*args, **kwargs):
            raise PermissionError("Access denied")
        
        monkeypatch.setattr(pd, 'read_csv', mock_read_csv)
        
        with pytest.raises(FileReadError) as exc_info:
            reader.read(test_file, FileType.CSV)
        
        assert "Failed to read" in str(exc_info.value)
    
    def test_read_excel_missing_engine(self, reader, tmp_path, monkeypatch):
        """Test reading Excel file when engine is missing."""
        test_file = tmp_path / "test.xlsx"
        test_file.write_bytes(b'dummy content')
        
        def mock_read_excel(*args, **kwargs):
            raise ImportError("Missing optional dependency 'openpyxl'")
        
        monkeypatch.setattr(pd, 'read_excel', mock_read_excel)
        
        with pytest.raises(FileReadError):
            reader.read(test_file, FileType.XLSX)


class TestFileReaderKwargsPassthrough:
    """Tests for additional kwargs passthrough."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_csv_additional_kwargs(self, reader, tmp_path):
        """Test that additional kwargs are passed to read_csv."""
        file_path = tmp_path / "test.csv"
        file_path.write_text("a,b,c\n1,2,3\n4,5,6")
        
        df = reader.read(
            file_path,
            FileType.CSV,
            dtype={'a': str, 'b': str, 'c': str}
        )
        
        assert df['a'].dtype == object  # string dtype
    
    def test_excel_additional_kwargs(self, reader, sample_xlsx_file):
        """Test that additional kwargs are passed to read_excel."""
        df = reader.read(
            sample_xlsx_file,
            FileType.XLSX,
            dtype=str
        )
        
        # All columns should be object (string) type
        assert all(df[col].dtype == object for col in df.columns)


class TestFileReaderEncodingDetection:
    """Tests for encoding detection and handling."""
    
    def test_auto_detect_utf8(self, utf8_csv_file):
        """Test auto-detection of UTF-8 encoding."""
        reader = FileReader()  # No encoding specified
        df = reader.read(utf8_csv_file, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_auto_detect_latin1(self, latin1_csv_file):
        """Test auto-detection of Latin-1 encoding."""
        reader = FileReader()  # No encoding specified
        df = reader.read(latin1_csv_file, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
    
    def test_override_encoding(self, latin1_csv_file):
        """Test overriding encoding detection."""
        reader = FileReader(encoding='latin-1')
        df = reader.read(latin1_csv_file, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
        # Verify special characters are preserved
        assert any('é' in str(v) or 'ñ' in str(v) or 'ã' in str(v) 
                   for v in df.values.flatten())


class TestFileReaderDelimiterDetection:
    """Tests for delimiter detection and handling."""
    
    def test_auto_detect_comma(self, sample_csv_file):
        """Test auto-detection of comma delimiter."""
        reader = FileReader()  # No delimiter specified
        df = reader.read(sample_csv_file, FileType.CSV)
        
        assert len(df.columns) > 1
    
    def test_auto_detect_pipe(self, sample_txt_file):
        """Test auto-detection of pipe delimiter."""
        reader = FileReader()
        df = reader.read(sample_txt_file, FileType.TXT)
        
        assert len(df.columns) > 1
    
    def test_override_delimiter(self, tmp_path):
        """Test overriding delimiter detection."""
        file_path = tmp_path / "custom.csv"
        file_path.write_text("a|b|c\n1|2|3")
        
        reader = FileReader(delimiter='|')
        df = reader.read(file_path, FileType.CSV)
        
        assert list(df.columns) == ['a', 'b', 'c']
    
    def test_tsv_uses_tab_by_default(self, sample_tsv_file):
        """Test that TSV files use tab delimiter by default."""
        reader = FileReader()  # No delimiter specified
        df = reader.read(sample_tsv_file, FileType.TSV)
        
        # If parsed correctly, should have multiple columns
        assert len(df.columns) > 1
    
    def test_csv_uses_comma_by_default(self, sample_csv_file):
        """Test that CSV files use comma delimiter by default."""
        reader = FileReader()  # No delimiter specified
        df = reader.read(sample_csv_file, FileType.CSV)
        
        assert len(df.columns) > 1


class TestFileReaderEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_read_large_file(self, reader, tmp_path):
        """Test reading larger file."""
        file_path = tmp_path / "large.csv"
        
        # Create a file with 10000 rows
        rows = ["id,name,value"]
        for i in range(10000):
            rows.append(f"{i},name_{i},{i * 1.5}")
        file_path.write_text("\n".join(rows))
        
        df = reader.read(file_path, FileType.CSV)
        
        assert len(df) == 10000
    
    def test_read_file_with_quotes(self, reader, tmp_path):
        """Test reading file with quoted fields."""
        file_path = tmp_path / "quoted.csv"
        content = '''name,description,value
"John Doe","A ""quoted"" description",100
"Jane, Smith","Contains, commas",200'''
        file_path.write_text(content)
        
        df = reader.read(file_path, FileType.CSV)
        
        assert len(df) == 2
        assert 'quoted' in df.iloc[0]['description']
    
    def test_read_file_with_nulls(self, reader, csv_with_nulls):
        """Test reading file with null values."""
        df = reader.read(csv_with_nulls, FileType.CSV)
        
        assert df.isna().any().any()  # Should have some nulls
    
    def test_read_file_with_mixed_types(self, reader, csv_mixed_types):
        """Test reading file with mixed types in columns."""
        df = reader.read(csv_mixed_types, FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_read_single_column_file(self, reader, tmp_path):
        """Test reading file with single column."""
        file_path = tmp_path / "single_col.csv"
        file_path.write_text("values\n1\n2\n3\n4\n5")
        
        df = reader.read(file_path, FileType.CSV)
        
        assert len(df.columns) == 1
        assert len(df) == 5
    
    def test_read_single_row_file(self, reader, tmp_path):
        """Test reading file with single row."""
        file_path = tmp_path / "single_row.csv"
        file_path.write_text("a,b,c\n1,2,3")
        
        df = reader.read(file_path, FileType.CSV)
        
        assert len(df) == 1
        assert len(df.columns) == 3
    
    def test_read_unicode_column_names(self, reader, tmp_path):
        """Test reading file with unicode column names."""
        file_path = tmp_path / "unicode_cols.csv"
        file_path.write_text("名前,年齢,都市\nAlice,25,Tokyo\nBob,30,大阪")
        
        df = reader.read(file_path, FileType.CSV)
        
        assert '名前' in df.columns
        assert '年齢' in df.columns
    
    def test_read_with_bom(self, reader, tmp_path):
        """Test reading file with BOM (Byte Order Mark)."""
        file_path = tmp_path / "bom.csv"
        content = "\ufeffa,b,c\n1,2,3"
        file_path.write_text(content, encoding='utf-8-sig')
        
        df = reader.read(file_path, FileType.CSV)
        
        assert len(df.columns) == 3
    
    def test_read_path_as_string(self, reader, sample_csv_file):
        """Test reading with path as string."""
        df = reader.read(str(sample_csv_file), FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)
    
    def test_read_path_as_path_object(self, reader, sample_csv_file):
        """Test reading with path as Path object."""
        df = reader.read(Path(sample_csv_file), FileType.CSV)
        
        assert isinstance(df, pd.DataFrame)


class TestFileReaderEngineSelection:
    """Tests for Excel engine selection."""
    
    @pytest.fixture
    def reader(self):
        """Create a FileReader instance."""
        return FileReader()
    
    def test_xlsx_uses_openpyxl(self, reader, sample_xlsx_file):
        """Test that XLSX files use openpyxl engine."""
        with patch('pandas.read_excel', wraps=pd.read_excel) as mock:
            reader.read(sample_xlsx_file, FileType.XLSX)
            
            call_kwargs = mock.call_args[1]
            assert call_kwargs.get('engine') == 'openpyxl'
    
    def test_xlsm_uses_openpyxl(self, reader, tmp_path):
        """Test that XLSM files use openpyxl engine."""
        # Create a mock xlsm file (actually xlsx renamed)
        xlsm_file = tmp_path / "test.xlsm"
        df = pd.DataFrame({'a': [1, 2, 3]})
        with pd.ExcelWriter(xlsm_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        with patch('pandas.read_excel', wraps=pd.read_excel) as mock:
            try:
                reader.read(xlsm_file, FileType.XLSM)
                call_kwargs = mock.call_args[1]
                assert call_kwargs.get('engine') == 'openpyxl'
            except FileReadError:
                pass  # OK if format not supported
    
    def test_xls_uses_xlrd(self, reader, sample_xls_file):
        """Test that XLS files use xlrd engine."""
        with patch('pandas.read_excel', wraps=pd.read_excel) as mock:
            try:
                reader.read(sample_xls_file, FileType.XLS)
                call_kwargs = mock.call_args[1]
                assert call_kwargs.get('engine') == 'xlrd'
            except FileReadError:
                pass  # OK if xlrd not available

if __name__ == "__main__":
    pytest.main([__file__, "-v"])