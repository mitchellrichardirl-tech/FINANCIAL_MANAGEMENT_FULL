import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO

import pandas as pd
from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest
from openpyxl.utils.exceptions import InvalidFileException

from src.statements.transaction_file import (
    TransactionFile,
    TransactionCsvFile,
    TransactionExcelFile
)


# ============== Fixtures ==============

@pytest.fixture
def app():
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config['MAX_FILE_SIZE'] = 10 * 1024 * 1024  # 10 MB
    return app


@pytest.fixture
def app_context(app):
    """Provide Flask app context for tests."""
    with app.app_context():
        yield app


@pytest.fixture
def mock_file_storage():
    """Create a mock FileStorage object."""
    mock_file = MagicMock()
    mock_file.filename = "test.csv"
    mock_file.tell.return_value = 1000
    mock_file.read.return_value = b"test,data\n1,2"
    return mock_file


@pytest.fixture
def sample_csv_content():
    """Sample CSV content as bytes."""
    return b"name,amount,date\nJohn,100,2024-01-15\nJane,200,2024-01-16"


@pytest.fixture
def sample_excel_content():
    """Sample Excel content as BytesIO."""
    df = pd.DataFrame({
        'name': ['John', 'Jane'],
        'amount': [100, 200],
        'date': ['2024-01-15', '2024-01-16']
    })
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer.getvalue()


# ============== Tests ==============

class TestTransactionFile:
    """Tests for TransactionFile abstract base class."""
    
    def test_cannot_instantiate_abstract_class(self):
        """Test that TransactionFile cannot be instantiated directly."""
        mock_file = MagicMock()
        
        with pytest.raises(TypeError) as exc_info:
            TransactionFile(mock_file)
        
        assert "abstract" in str(exc_info.value).lower()
    
    def test_skip_rows_calculation_with_start_row_1(self, mock_file_storage):
        """Test skip_rows is 0 when start_row is 1."""
        csv_file = TransactionCsvFile(mock_file_storage, start_row=1)
        assert csv_file.skip_rows == 0
    
    def test_skip_rows_calculation_with_start_row_5(self, mock_file_storage):
        """Test skip_rows is 4 when start_row is 5."""
        csv_file = TransactionCsvFile(mock_file_storage, start_row=5)
        assert csv_file.skip_rows == 4
    
    def test_skip_rows_calculation_with_start_row_0(self, mock_file_storage):
        """Test skip_rows is 0 when start_row is 0."""
        csv_file = TransactionCsvFile(mock_file_storage, start_row=0)
        assert csv_file.skip_rows == 0
    
    def test_skip_rows_calculation_with_negative_start_row(self, mock_file_storage):
        """Test skip_rows is 0 when start_row is negative."""
        csv_file = TransactionCsvFile(mock_file_storage, start_row=-5)
        assert csv_file.skip_rows == 0


class TestTransactionFileExtractContent:
    """Tests for _extract_content method."""
    
    def test_extract_content_success(
        self, app_context, mock_file_storage, sample_csv_content
    ):
        """Test successful content extraction."""
        mock_file_storage.read.return_value = sample_csv_content
        
        csv_file = TransactionCsvFile(mock_file_storage)
        csv_file._extract_content()
        
        assert csv_file.file_content == sample_csv_content
        assert isinstance(csv_file.file_stream, BytesIO)
        mock_file_storage.seek.assert_any_call(0, 2)
        mock_file_storage.seek.assert_any_call(0)
    
    def test_extract_content_file_too_large(self, app_context, mock_file_storage):
        """Test RequestEntityTooLarge raised when file exceeds max size."""
        mock_file_storage.tell.return_value = 20 * 1024 * 1024  # 20 MB
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with pytest.raises(RequestEntityTooLarge) as exc_info:
            csv_file._extract_content()
        
        assert "exceeds maximum" in str(exc_info.value.description)
    
    def test_extract_content_uses_custom_max_size(self, app, mock_file_storage):
        """Test that config MAX_FILE_SIZE is used."""
        app.config['MAX_FILE_SIZE'] = 5 * 1024 * 1024  # 5 MB
        mock_file_storage.tell.return_value = 6 * 1024 * 1024  # 6 MB
        
        with app.app_context():
            csv_file = TransactionCsvFile(mock_file_storage)
            
            with pytest.raises(RequestEntityTooLarge):
                csv_file._extract_content()
    
    def test_extract_content_file_read_error(
        self, app_context, mock_file_storage
    ):
        """Test exception handling when file read fails."""
        mock_file_storage.read.side_effect = IOError("Disk read error")
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with pytest.raises(IOError) as exc_info:
            csv_file._extract_content()
        
        assert "Disk read error" in str(exc_info.value)


class TestTransactionCsvFile:
    """Tests for TransactionCsvFile."""
    
    def test_process_csv_utf8_success(
        self, app_context, mock_file_storage, sample_csv_content
    ):
        """Test successful CSV processing with UTF-8 encoding."""
        mock_file_storage.read.return_value = sample_csv_content
        
        csv_file = TransactionCsvFile(mock_file_storage)
        df = csv_file.process_file()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ['name', 'amount', 'date']
        assert df.iloc[0]['name'] == 'John'
    
    def test_process_csv_windows1252_encoding(
        self, app_context, mock_file_storage
    ):
        """Test CSV processing with Windows-1252 encoding."""
        windows_content = "name,amount\nJohn,€100".encode('Windows-1252')
        mock_file_storage.read.return_value = windows_content
        
        csv_file = TransactionCsvFile(mock_file_storage)
        df = csv_file.process_file()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
    
    def test_process_csv_with_skip_rows(
        self, app_context, mock_file_storage
    ):
        """Test CSV processing with skip_rows."""
        content = b"header1\nheader2\nname,amount\nJohn,100\nJane,200"
        mock_file_storage.read.return_value = content
        
        csv_file = TransactionCsvFile(mock_file_storage, start_row=3)
        df = csv_file.process_file()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ['name', 'amount']
    
    def test_process_csv_empty_file_raises_bad_request(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest raised for empty CSV."""
        mock_file_storage.read.return_value = b""
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with pytest.raises(BadRequest) as exc_info:
            csv_file.process_file()
        
        assert "empty" in str(exc_info.value.description).lower()
    
    def test_process_csv_parser_error_raises_bad_request(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest raised for malformed CSV."""
        malformed_content = b'name,amount\n"John,100,extra\nJane'
        mock_file_storage.read.return_value = malformed_content
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with pytest.raises(BadRequest) as exc_info:
            csv_file.process_file()
        
        assert "parsing error" in str(exc_info.value.description).lower()
    
    def test_process_csv_unsupported_encoding_raises_bad_request(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest raised when no encoding works."""
        mock_file_storage.read.return_value = b"\x80\x81\x82\x83"
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with patch('pandas.read_csv') as mock_read_csv:
            mock_read_csv.side_effect = UnicodeDecodeError(
                'utf-8', b'', 0, 1, 'invalid'
            )
            
            with pytest.raises(BadRequest) as exc_info:
                csv_file.process_file()
            
            assert "could not decode" in str(exc_info.value.description).lower()
    
    def test_process_csv_tries_multiple_encodings(
        self, app_context, mock_file_storage
    ):
        """Test that CSV processor tries all encodings in order."""
        mock_file_storage.read.return_value = b"name,amount\nJohn,100"
        
        csv_file = TransactionCsvFile(mock_file_storage)
        
        with patch('pandas.read_csv') as mock_read_csv:
            mock_read_csv.side_effect = [
                UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid'),
                UnicodeDecodeError('Windows-1252', b'', 0, 1, 'invalid'),
                pd.DataFrame({'name': ['John'], 'amount': [100]})
            ]
            
            df = csv_file.process_file()
            
            assert mock_read_csv.call_count == 3
            assert isinstance(df, pd.DataFrame)


class TestTransactionExcelFile:
    """Tests for TransactionExcelFile."""
    
    def test_process_excel_openpyxl_success(
        self, app_context, mock_file_storage, sample_excel_content
    ):
        """Test successful Excel processing with openpyxl."""
        mock_file_storage.read.return_value = sample_excel_content
        
        excel_file = TransactionExcelFile(mock_file_storage)
        df = excel_file.process_file()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'name' in df.columns
        assert 'amount' in df.columns
    
    def test_process_excel_with_skip_rows(
        self, app_context, mock_file_storage, sample_excel_content
    ):
        """Test Excel processing with skip_rows."""
        mock_file_storage.read.return_value = sample_excel_content
        
        excel_file = TransactionExcelFile(mock_file_storage, start_row=2)
        df = excel_file.process_file()
        
        assert isinstance(df, pd.DataFrame)
    
    def test_process_excel_falls_back_to_xlrd(
        self, app_context, mock_file_storage
    ):
        """Test fallback to xlrd engine for .xls files."""
        mock_file_storage.read.return_value = b"fake excel content"
        
        excel_file = TransactionExcelFile(mock_file_storage)
        
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.side_effect = [
                InvalidFileException("Not a valid .xlsx file"),
                pd.DataFrame({'name': ['John'], 'amount': [100]})
            ]
            
            df = excel_file.process_file()
            
            assert mock_read_excel.call_count == 2
            assert mock_read_excel.call_args_list[0][1]['engine'] == 'openpyxl'
            assert mock_read_excel.call_args_list[1][1]['engine'] == 'xlrd'
            assert isinstance(df, pd.DataFrame)
    
    def test_process_excel_xlrd_not_installed(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest when xlrd is not installed for .xls files."""
        mock_file_storage.read.return_value = b"fake xls content"
        
        excel_file = TransactionExcelFile(mock_file_storage)
        
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.side_effect = [
                InvalidFileException("Not a valid .xlsx file"),
                ImportError("No module named 'xlrd'")
            ]
            
            with pytest.raises(BadRequest) as exc_info:
                excel_file.process_file()
            
            assert "xlrd engine is not installed" in str(exc_info.value.description)
    
    def test_process_excel_xlrd_processing_error(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest when xlrd fails to process file."""
        mock_file_storage.read.return_value = b"fake xls content"
        
        excel_file = TransactionExcelFile(mock_file_storage)
        
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.side_effect = [
                InvalidFileException("Not a valid .xlsx file"),
                ValueError("Corrupted Excel file")
            ]
            
            with pytest.raises(BadRequest) as exc_info:
                excel_file.process_file()
            
            assert "Error processing Excel content" in str(exc_info.value.description)
    
    def test_process_excel_openpyxl_generic_error(
        self, app_context, mock_file_storage
    ):
        """Test BadRequest for generic openpyxl errors."""
        mock_file_storage.read.return_value = b"corrupt content"
        
        excel_file = TransactionExcelFile(mock_file_storage)
        
        with patch('pandas.read_excel') as mock_read_excel:
            mock_read_excel.side_effect = ValueError("Corrupted workbook")
            
            with pytest.raises(BadRequest) as exc_info:
                excel_file.process_file()
            
            assert "Error processing Excel content" in str(exc_info.value.description)


class TestTransactionFileIntegration:
    """Integration tests for TransactionFile classes."""
    
    def test_csv_file_end_to_end(self, app_context):
        """Test complete CSV file processing flow."""
        csv_content = b"name,amount,date\nAlice,150,2024-01-01\nBob,250,2024-01-02"
        
        mock_file = MagicMock()
        mock_file.filename = "transactions.csv"
        mock_file.tell.return_value = len(csv_content)
        mock_file.read.return_value = csv_content
        
        csv_file = TransactionCsvFile(mock_file)
        df = csv_file.process_file()
        
        assert len(df) == 2
        assert df.iloc[0]['name'] == 'Alice'
        assert df.iloc[1]['name'] == 'Bob'
        assert df.iloc[0]['amount'] == 150
    
    def test_excel_file_end_to_end(self, app_context, sample_excel_content):
        """Test complete Excel file processing flow."""
        mock_file = MagicMock()
        mock_file.filename = "transactions.xlsx"
        mock_file.tell.return_value = len(sample_excel_content)
        mock_file.read.return_value = sample_excel_content
        
        excel_file = TransactionExcelFile(mock_file)
        df = excel_file.process_file()
        
        assert len(df) == 2
        assert 'name' in df.columns
        assert 'amount' in df.columns

if __name__ == "__main__":
    pytest.main([__file__, "-v"])