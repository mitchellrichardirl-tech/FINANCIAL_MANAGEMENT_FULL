import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.database.repositories.uploads import UploadRepository
from src.database.connection import DatabaseError


class TestUploadRepositoryInit:
    """Tests for UploadRepository initialization."""
    
    def test_init_with_existing_manager(self, mock_db_manager):
        """Test initialization with existing database manager."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            repo = UploadRepository()
            assert repo.db == mock_db_manager
    
    def test_init_without_manager_initializes_new(self, mock_db_manager):
        """Test initialization creates new connection if none exists."""
        with patch('src.database.repositories.uploads.get_manager', side_effect=DatabaseError("No manager")):
            with patch('src.database.repositories.uploads.initialize_db_connection', return_value=mock_db_manager):
                repo = UploadRepository()
                assert repo.db == mock_db_manager


class TestCreateUpload:
    """Tests for create_upload method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_create_upload_basic(self, repo, mock_db_manager):
        """Test creating a basic upload record."""
        mock_cursor = Mock()
        mock_cursor.lastrowid = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        upload_id = repo.create_upload(
            filename='test.csv',
            file_type='csv',
            row_count=10,
            column_count=3
        )
        
        assert upload_id == 1
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert 'INSERT INTO uploads' in call_args[0][0]
        assert call_args[0][1] == ('test.csv', 'csv', 10, 3, None)
    
    def test_create_upload_with_columns(self, repo, mock_db_manager):
        """Test creating upload with column names."""
        mock_cursor = Mock()
        mock_cursor.lastrowid = 2
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        columns = ['id', 'name', 'value']
        upload_id = repo.create_upload(
            filename='test.xlsx',
            file_type='xlsx',
            row_count=100,
            column_count=3,
            columns=columns
        )
        
        assert upload_id == 2
        call_args = mock_cursor.execute.call_args[0][1]
        assert call_args[0] == 'test.xlsx'
        assert call_args[1] == 'xlsx'
        assert call_args[4] == json.dumps(columns)
    
    def test_create_upload_default_counts(self, repo, mock_db_manager):
        """Test creating upload with default row/column counts."""
        mock_cursor = Mock()
        mock_cursor.lastrowid = 3
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        upload_id = repo.create_upload(
            filename='default.csv',
            file_type='csv'
        )
        
        assert upload_id == 3
        call_args = mock_cursor.execute.call_args[0][1]
        assert call_args[2] == 0  # row_count
        assert call_args[3] == 0  # column_count
    
    def test_create_upload_integrity_error(self, repo, mock_db_manager):
        """Test handling of integrity errors."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = sqlite3.IntegrityError("Constraint violation")
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.create_upload('test.csv', 'csv')
        
        assert "Failed to create upload" in str(exc_info.value)
    
    def test_create_upload_generic_error(self, repo, mock_db_manager):
        """Test handling of generic errors."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.create_upload('test.csv', 'csv')
        
        assert "Failed to create upload" in str(exc_info.value)


class TestGetUploadById:
    """Tests for get_upload_by_id method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_upload_by_id_found(self, repo, mock_db_manager):
        """Test getting an existing upload."""
        mock_cursor = Mock()
        mock_row = {
            'id': 1,
            'filename': 'test.csv',
            'file_type': 'csv',
            'row_count': 10,
            'column_count': 3,
            'columns': json.dumps(['a', 'b', 'c']),
            'upload_date': '2024-01-01T00:00:00'
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.get_upload_by_id(1)
        
        assert result is not None
        assert result['id'] == 1
        assert result['filename'] == 'test.csv'
        assert result['columns'] == ['a', 'b', 'c']
    
    def test_get_upload_by_id_not_found(self, repo, mock_db_manager):
        """Test getting a non-existent upload."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.get_upload_by_id(999)
        
        assert result is None
    
    def test_get_upload_by_id_no_columns(self, repo, mock_db_manager):
        """Test getting upload with no columns."""
        mock_cursor = Mock()
        mock_row = {
            'id': 1,
            'filename': 'test.csv',
            'file_type': 'csv',
            'row_count': 10,
            'column_count': 3,
            'columns': None,
            'upload_date': '2024-01-01T00:00:00'
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.get_upload_by_id(1)
        
        assert result is not None
        assert result['columns'] is None
    
    def test_get_upload_by_id_error(self, repo, mock_db_manager):
        """Test error handling when getting upload."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError):
            repo.get_upload_by_id(1)


class TestGetAllUploads:
    """Tests for get_all_uploads method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_all_uploads_no_filters(self, repo, mock_db_manager):
        """Test getting all uploads without filters."""
        mock_cursor = Mock()
        mock_rows = [
            {'id': 1, 'filename': 'test1.csv', 'file_type': 'csv', 'columns': None},
            {'id': 2, 'filename': 'test2.xlsx', 'file_type': 'xlsx', 'columns': None}
        ]
        mock_cursor.fetchall.return_value = mock_rows
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        results = repo.get_all_uploads()
        
        assert len(results) == 2
        assert results[0]['id'] == 1
        assert results[1]['id'] == 2
    
    def test_get_all_uploads_with_limit_offset(self, repo, mock_db_manager):
        """Test pagination with limit and offset."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [{'id': 6, 'filename': 'test.csv', 'columns': None}]
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        results = repo.get_all_uploads(limit=10, offset=5)
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'LIMIT ? OFFSET ?' in call_args[0]
        assert 10 in call_args[1]
        assert 5 in call_args[1]
    
    def test_get_all_uploads_filter_by_file_type(self, repo, mock_db_manager):
        """Test filtering by file type."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        repo.get_all_uploads(file_type='csv')
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'file_type = ?' in call_args[0]
        assert 'csv' in call_args[1]
    
    def test_get_all_uploads_filter_by_filename(self, repo, mock_db_manager):
        """Test filtering by filename (partial match)."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        repo.get_all_uploads(filename='test')
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'filename LIKE ?' in call_args[0]
        assert '%test%' in call_args[1]
    
    def test_get_all_uploads_filter_by_date_range(self, repo, mock_db_manager):
        """Test filtering by date range."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)
        
        repo.get_all_uploads(start_date=start_date, end_date=end_date)
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'upload_date >= ?' in call_args[0]
        assert 'upload_date <= ?' in call_args[0]
    
    def test_get_all_uploads_multiple_filters(self, repo, mock_db_manager):
        """Test with multiple filters combined."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        repo.get_all_uploads(
            file_type='csv',
            filename='test',
            start_date=datetime(2024, 1, 1)
        )
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'file_type = ?' in call_args[0]
        assert 'filename LIKE ?' in call_args[0]
        assert 'upload_date >= ?' in call_args[0]
        assert len(call_args[1]) == 5  # 3 filters + limit + offset


class TestUpdateUpload:
    """Tests for update_upload method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_update_upload_filename(self, repo, mock_db_manager):
        """Test updating filename."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with patch.object(repo, 'get_upload_by_id', return_value={'id': 1, 'filename': 'new.csv'}):
            result = repo.update_upload(1, filename='new.csv')
        
        assert result is not None
        call_args = mock_cursor.execute.call_args[0]
        assert 'UPDATE uploads SET' in call_args[0]
        assert 'filename = ?' in call_args[0]
    
    def test_update_upload_multiple_fields(self, repo, mock_db_manager):
        """Test updating multiple fields."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with patch.object(repo, 'get_upload_by_id', return_value={'id': 1}):
            result = repo.update_upload(
                1,
                filename='updated.csv',
                file_type='csv',
                row_count=20,
                column_count=5
            )
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'filename = ?' in call_args[0]
        assert 'file_type = ?' in call_args[0]
        assert 'row_count = ?' in call_args[0]
        assert 'column_count = ?' in call_args[0]
    
    def test_update_upload_columns(self, repo, mock_db_manager):
        """Test updating columns list."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        new_columns = ['a', 'b', 'c', 'd']
        
        with patch.object(repo, 'get_upload_by_id', return_value={'id': 1}):
            result = repo.update_upload(1, columns=new_columns)
        
        call_args = mock_cursor.execute.call_args[0]
        assert json.dumps(new_columns) in call_args[1]
    
    def test_update_upload_no_changes(self, repo, mock_db_manager):
        """Test update with no changes returns current record."""
        with patch.object(repo, 'get_upload_by_id', return_value={'id': 1}) as mock_get:
            result = repo.update_upload(1)
        
        assert result is not None
        mock_get.assert_called_with(1)
    
    def test_update_upload_not_found(self, repo, mock_db_manager):
        """Test updating non-existent upload."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.update_upload(999, filename='test.csv')
        
        assert result is None
    
    def test_update_upload_error(self, repo, mock_db_manager):
        """Test error handling during update."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError):
            repo.update_upload(1, filename='test.csv')


class TestDeleteUpload:
    """Tests for delete_upload method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_delete_upload_success(self, repo, mock_db_manager):
        """Test successful upload deletion."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.delete_upload(1)
        
        assert result is True
        mock_cursor.execute.assert_called_once()
        assert 'DELETE FROM uploads WHERE id = ?' in mock_cursor.execute.call_args[0][0]
    
    def test_delete_upload_not_found(self, repo, mock_db_manager):
        """Test deleting non-existent upload."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.delete_upload(999)
        
        assert result is False
    
    def test_delete_upload_error(self, repo, mock_db_manager):
        """Test error handling during deletion."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError):
            repo.delete_upload(1)


class TestCountUploads:
    """Tests for count_uploads method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_count_uploads_no_filters(self, repo, mock_db_manager):
        """Test counting all uploads."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (42,)
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.count_uploads()
        
        assert count == 42
    
    def test_count_uploads_with_filters(self, repo, mock_db_manager):
        """Test counting with filters."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (10,)
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.count_uploads(
            file_type='csv',
            start_date=datetime(2024, 1, 1)
        )
        
        assert count == 10
        call_args = mock_cursor.execute.call_args[0]
        assert 'WHERE' in call_args[0]


class TestSaveUploadData:
    """Tests for save_upload_data method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_save_upload_data_small_batch(self, repo, mock_db_manager):
        """Test saving data in single batch."""
        mock_cursor = Mock()
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        rows = [
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'},
            {'id': 3, 'name': 'Charlie'}
        ]
        
        count = repo.save_upload_data(1, rows)
        
        assert count == 3
        mock_cursor.executemany.assert_called_once()
        call_args = mock_cursor.executemany.call_args[0]
        assert 'INSERT INTO upload_data' in call_args[0]
        assert len(call_args[1]) == 3
    
    def test_save_upload_data_multiple_batches(self, repo, mock_db_manager):
        """Test saving data in multiple batches."""
        mock_cursor = Mock()
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        rows = [{'id': i} for i in range(2500)]
        
        count = repo.save_upload_data(1, rows, batch_size=1000)
        
        assert count == 2500
        # Should be called 3 times (1000, 1000, 500)
        assert mock_cursor.executemany.call_count == 3
    
    def test_save_upload_data_preserves_row_index(self, repo, mock_db_manager):
        """Test that row indices are preserved correctly."""
        mock_cursor = Mock()
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        rows = [{'value': f'row{i}'} for i in range(5)]
        
        repo.save_upload_data(1, rows)
        
        call_args = mock_cursor.executemany.call_args[0][1]
        # Check indices are 0, 1, 2, 3, 4
        assert call_args[0][1] == 0
        assert call_args[4][1] == 4
    
    def test_save_upload_data_integrity_error(self, repo, mock_db_manager):
        """Test handling integrity errors."""
        mock_cursor = Mock()
        mock_cursor.executemany.side_effect = sqlite3.IntegrityError("FK violation")
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        with pytest.raises(DatabaseError):
            repo.save_upload_data(1, [{'id': 1}])
    
    def test_save_upload_data_empty_list(self, repo, mock_db_manager):
        """Test saving empty data list."""
        mock_cursor = Mock()
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.save_upload_data(1, [])
        
        assert count == 0


class TestGetUploadData:
    """Tests for get_upload_data method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_upload_data_all(self, repo, mock_db_manager):
        """Test getting all upload data."""
        mock_cursor = Mock()
        mock_rows = [
            {'id': 1, 'upload_id': 1, 'row_index': 0, 'row_data': '{"id": 1}'},
            {'id': 2, 'upload_id': 1, 'row_index': 1, 'row_data': '{"id": 2}'}
        ]
        mock_cursor.fetchall.return_value = mock_rows
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        results = repo.get_upload_data(1)
        
        assert len(results) == 2
        assert results[0]['row_data'] == {'id': 1}
    
    def test_get_upload_data_with_limit(self, repo, mock_db_manager):
        """Test getting data with limit."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        repo.get_upload_data(1, limit=10, offset=5)
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'LIMIT ? OFFSET ?' in call_args[0]
        assert 10 in call_args[1]
        assert 5 in call_args[1]
    
    def test_get_upload_data_with_row_range(self, repo, mock_db_manager):
        """Test getting data with row range."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        repo.get_upload_data(1, start_row=10, end_row=20)
        
        call_args = mock_cursor.execute.call_args[0]
        assert 'row_index >= ?' in call_args[0]
        assert 'row_index <= ?' in call_args[0]


class TestGetUploadDataRow:
    """Tests for get_upload_data_row method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_upload_data_row_found(self, repo, mock_db_manager):
        """Test getting existing data row."""
        mock_cursor = Mock()
        mock_row = {
            'id': 1,
            'upload_id': 1,
            'row_index': 5,
            'row_data': '{"name": "Alice", "age": 30}'
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.get_upload_data_row(1, 5)
        
        assert result is not None
        assert result['row_index'] == 5
        assert result['row_data']['name'] == 'Alice'
    
    def test_get_upload_data_row_not_found(self, repo, mock_db_manager):
        """Test getting non-existent data row."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.get_upload_data_row(1, 999)
        
        assert result is None


class TestUpdateUploadDataRow:
    """Tests for update_upload_data_row method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_update_upload_data_row_success(self, repo, mock_db_manager):
        """Test updating data row successfully."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        new_data = {'name': 'Bob', 'age': 25}
        
        with patch.object(repo, 'get_upload_data_row', return_value={'row_data': new_data}):
            result = repo.update_upload_data_row(1, 5, new_data)
        
        assert result is not None
        call_args = mock_cursor.execute.call_args[0]
        assert 'UPDATE upload_data' in call_args[0]
        assert json.dumps(new_data) in call_args[1]
    
    def test_update_upload_data_row_not_found(self, repo, mock_db_manager):
        """Test updating non-existent row."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        result = repo.update_upload_data_row(1, 999, {})
        
        assert result is None


class TestDeleteUploadData:
    """Tests for delete_upload_data method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_delete_upload_data_success(self, repo, mock_db_manager):
        """Test deleting upload data."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 100
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.delete_upload_data(1)
        
        assert count == 100
        mock_cursor.execute.assert_called_once()
    
    def test_delete_upload_data_no_rows(self, repo, mock_db_manager):
        """Test deleting when no data exists."""
        mock_cursor = Mock()
        mock_cursor.rowcount = 0
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.delete_upload_data(999)
        
        assert count == 0


class TestCountUploadDataRows:
    """Tests for count_upload_data_rows method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_count_upload_data_rows(self, repo, mock_db_manager):
        """Test counting data rows."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (250,)
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        count = repo.count_upload_data_rows(1)
        
        assert count == 250


class TestCreateUploadWithData:
    """Tests for create_upload_with_data method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_create_upload_with_data_success(self, repo, mock_db_manager):
        """Test creating upload with data in single transaction."""
        mock_cursor = Mock()
        mock_cursor.lastrowid = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        columns = ['id', 'name']
        rows = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
        
        result = repo.create_upload_with_data(
            filename='test.csv',
            file_type='csv',
            columns=columns,
            rows=rows
        )
        
        assert result['upload_id'] == 1
        assert result['rows_inserted'] == 2
        assert mock_cursor.execute.call_count == 1
        assert mock_cursor.executemany.call_count == 1
    
    def test_create_upload_with_data_large_dataset(self, repo, mock_db_manager):
        """Test creating upload with large dataset (multiple batches)."""
        mock_cursor = Mock()
        mock_cursor.lastrowid = 1
        mock_db_manager.transaction.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        columns = ['id']
        rows = [{'id': i} for i in range(2500)]
        
        result = repo.create_upload_with_data(
            filename='large.csv',
            file_type='csv',
            columns=columns,
            rows=rows,
            batch_size=1000
        )
        
        assert result['rows_inserted'] == 2500
        # 1 for upload, 3 for data batches
        assert mock_cursor.executemany.call_count == 3


class TestGetUploadWithData:
    """Tests for get_upload_with_data method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_upload_with_data_found(self, repo):
        """Test getting upload with its data."""
        mock_upload = {'id': 1, 'filename': 'test.csv'}
        mock_data = [{'row_index': 0, 'row_data': {}}, {'row_index': 1, 'row_data': {}}]
        
        with patch.object(repo, 'get_upload_by_id', return_value=mock_upload):
            with patch.object(repo, 'get_upload_data', return_value=mock_data):
                result = repo.get_upload_with_data(1)
        
        assert result is not None
        assert 'data' in result
        assert len(result['data']) == 2
    
    def test_get_upload_with_data_not_found(self, repo):
        """Test getting non-existent upload with data."""
        with patch.object(repo, 'get_upload_by_id', return_value=None):
            result = repo.get_upload_with_data(999)
        
        assert result is None
    
    def test_get_upload_with_data_pagination(self, repo):
        """Test getting upload with paginated data."""
        mock_upload = {'id': 1, 'filename': 'test.csv'}
        
        with patch.object(repo, 'get_upload_by_id', return_value=mock_upload):
            with patch.object(repo, 'get_upload_data', return_value=[]) as mock_get_data:
                result = repo.get_upload_with_data(1, data_limit=10, data_offset=5)
        
        mock_get_data.assert_called_once_with(1, limit=10, offset=5)


class TestGetUploadStats:
    """Tests for get_upload_stats method."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_get_upload_stats(self, repo, mock_db_manager):
        """Test getting upload statistics."""
        mock_cursor = Mock()
        
        # Mock different query results
        mock_cursor.fetchone.side_effect = [
            {
                'total_uploads': 100,
                'total_rows': 10000,
                'avg_rows_per_upload': 100.0,
                'avg_columns': 5.0,
                'earliest_upload': '2024-01-01',
                'latest_upload': '2024-12-31'
            }
        ]
        mock_cursor.fetchall.side_effect = [
            [{'file_type': 'csv', 'count': 60, 'total_rows': 6000}],
            [{'id': 1, 'filename': 'recent.csv'}]
        ]
        
        mock_db_manager.get_connection.return_value.__enter__.return_value.cursor.return_value = mock_cursor
        
        stats = repo.get_upload_stats()
        
        assert stats['total_uploads'] == 100
        assert 'by_file_type' in stats
        assert 'recent_uploads' in stats


class TestHelperMethods:
    """Tests for helper methods."""
    
    @pytest.fixture
    def repo(self, mock_db_manager):
        """Create repository with mocked database."""
        with patch('src.database.repositories.uploads.get_manager', return_value=mock_db_manager):
            return UploadRepository()
    
    def test_row_to_dict_with_columns(self, repo):
        """Test converting row with columns JSON."""
        mock_row = {
            'id': 1,
            'filename': 'test.csv',
            'columns': json.dumps(['a', 'b', 'c'])
        }
        
        result = repo._row_to_dict(mock_row)
        
        assert result['id'] == 1
        assert result['columns'] == ['a', 'b', 'c']
    
    def test_row_to_dict_invalid_json(self, repo):
        """Test handling invalid JSON in columns."""
        mock_row = {
            'id': 1,
            'columns': 'invalid json'
        }
        
        result = repo._row_to_dict(mock_row)
        
        assert result['columns'] == []
    
    def test_row_to_dict_null_columns(self, repo):
        """Test handling null columns."""
        mock_row = {
            'id': 1,
            'columns': None
        }
        
        result = repo._row_to_dict(mock_row)
        
        assert result['columns'] is None
    
    def test_data_row_to_dict(self, repo):
        """Test converting data row."""
        mock_row = {
            'id': 1,
            'row_index': 0,
            'row_data': '{"name": "Alice", "age": 30}'
        }
        
        result = repo._data_row_to_dict(mock_row)
        
        assert result['row_data'] == {'name': 'Alice', 'age': 30}
    
    def test_data_row_to_dict_invalid_json(self, repo):
        """Test handling invalid JSON in row_data."""
        mock_row = {
            'id': 1,
            'row_data': 'invalid json'
        }
        
        result = repo._data_row_to_dict(mock_row)
        
        assert result['row_data'] == {}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])