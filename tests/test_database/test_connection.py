import pytest
import sqlite3
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.database.connection import ConnectionManager, DatabaseError
from src.models.receipt import Receipt

@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path"""
    return tmp_path / "test.db"


@pytest.fixture
def connection_manager(temp_db_path):
    """Create a test database instance"""
    return ConnectionManager(temp_db_path)

class TestConnectionManagerInitialization:
    """Test database initialization and setup"""
    
    def test_init_creates_database_file(self, temp_db_path):
        """Test that database file is created on first connection"""
        manager = ConnectionManager(temp_db_path)
        
        # File doesn't exist until first connection
        assert not temp_db_path.exists()
        
        # File created on first connection
        with manager.get_connection():
            pass
        
        assert temp_db_path.exists()
    
    def test_init_creates_directory(self, tmp_path):
        """Test that parent directories are created"""
        nested_path = tmp_path / "nested" / "dir" / "test.db"
        db = ConnectionManager(nested_path)

        # File created on first connection
        with db.get_connection():
            pass

        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_init_with_string_path(self, tmp_path):
        """Test initialization with string path"""
        db_path = str(tmp_path / "test.db")
        db = ConnectionManager(db_path)

        # File created on first connection
        with db.get_connection():
            pass

        assert Path(db_path).exists()

    def test_foreign_keys_enabled(self, connection_manager):
        """Test that foreign keys are enabled"""
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()[0]
            assert result == 1
    
    def test_wal_mode_enabled(self, connection_manager):
        """Test that WAL mode is enabled"""
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.upper() == 'WAL'

class TestConnectionManagement:
    """Test database connection management"""
    
    def test_get_connection_returns_connection(self, connection_manager):
        """Test that get_connection returns a valid connection"""
        with connection_manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
    
    def test_connection_closed_after_context(self, connection_manager):
        """Test that connection is closed after context manager exits"""
        with connection_manager.get_connection() as conn:
            pass
        
        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_connection_timeout(self, temp_db_path):
        """Test connection timeout setting"""
        db = ConnectionManager(temp_db_path)
        with db.get_connection() as conn:
            # Just verify connection can be created with timeout
            assert conn is not None

class TestBackup:
    """Test database backup functionality"""
    
    def test_backup_creates_file(self, connection_manager, tmp_path):
        """Test that backup creates a file"""
        # Create some data to backup
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")
            conn.commit()
        
        backup_path = tmp_path / "backup.db"
        connection_manager.backup(backup_path)
        
        assert backup_path.exists()
    
    def test_backup_contains_data(self, connection_manager, tmp_path):
        """Test that backup contains the same data"""
        # Create some data
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'test')")
            conn.commit()
        
        backup_path = tmp_path / "backup.db"
        connection_manager.backup(backup_path)
        
        # Verify backup contains the data
        backup_manager = ConnectionManager(backup_path)
        with backup_manager.get_connection() as conn:
            result = conn.execute("SELECT * FROM test").fetchone()
            assert result[0] == 1
            assert result[1] == 'test'
    
    def test_backup_creates_parent_directories(self, connection_manager, tmp_path):
        """Test that backup creates parent directories"""
        # Ensure database file exists
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
        
        backup_path = tmp_path / "nested" / "dir" / "backup.db"
        connection_manager.backup(backup_path)
        
        assert backup_path.exists()
        assert backup_path.parent.exists()
    
    def test_backup_with_string_path(self, connection_manager, tmp_path):
        """Test backup with string path"""
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
        
        backup_path = str(tmp_path / "backup.db")
        connection_manager.backup(backup_path)
        
        assert Path(backup_path).exists()

class TestErrorHandling:
    """Test error handling"""

    def test_database_error_on_invalid_connection(self, tmp_path):
        """Test error handling with invalid database path"""
        # Create a file where directory should be
        bad_path = tmp_path / "file.txt"
        bad_path.write_text("content")
        db_path = bad_path / "test.db"  # Can't create DB under a file
        
        # Should handle gracefully
        with pytest.raises(Exception):  # Could be OSError or DatabaseError
            db = ConnectionManager(db_path)

    def test_backup_handles_invalid_path(self, connection_manager):
        """Test backup error handling with invalid path"""
        with pytest.raises(DatabaseError):
            connection_manager.backup("/invalid/nonexistent/path/backup.db")

class TestConcurrency:
    """Test concurrent operations"""
    
    def test_multiple_connections_read(self, connection_manager):
        """Test reading from multiple connections"""
        # Setup test data
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test VALUES (1, 'test_data')")
            conn.commit()
        
        # Read from different connections
        with connection_manager.get_connection() as conn1:
            cursor1 = conn1.cursor()
            cursor1.execute("SELECT * FROM test WHERE id = ?", (1,))
            result1 = cursor1.fetchone()
        
        with connection_manager.get_connection() as conn2:
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT * FROM test WHERE id = ?", (1,))
            result2 = cursor2.fetchone()
        
        assert dict(result1) == dict(result2)
        assert result1['value'] == 'test_data'
    
    def test_wal_mode_allows_concurrent_reads(self, connection_manager):
        """Test that WAL mode allows concurrent reads"""
        # Setup test data
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            for i in range(5):
                conn.execute("INSERT INTO test VALUES (?, ?)", (i, f"value_{i}"))
            conn.commit()
        
        # Multiple reads should work
        with connection_manager.get_connection() as conn:
            count1 = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
        
        with connection_manager.get_connection() as conn:
            count2 = conn.execute("SELECT COUNT(*) FROM test").fetchone()[0]
        
        assert count1 == count2 == 5

class TestConnectionManager:
    def test_transaction_commits_on_success(self, connection_manager):
        """Test that transaction auto-commits"""
        with connection_manager.transaction() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")
        
        # Verify commit happened
        with connection_manager.get_connection() as conn:
            result = conn.execute("SELECT * FROM test").fetchone()
            assert result[0] == 1
    
    def test_transaction_rollback_on_error(self, connection_manager):
        """Test that transaction rolls back on exception"""
        with connection_manager.get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
        
        with pytest.raises(Exception):
            with connection_manager.transaction() as conn:
                conn.execute("INSERT INTO test VALUES (1)")
                raise ValueError("Simulated error")
        
        # Verify rollback happened
        with connection_manager.get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result[0] == 0


class TestModuleLevelFunctions:
    def test_get_manager_before_init_raises_error(self):
        """Test that get_manager fails if not initialized"""
        # Reset global state first
        import src.database.connection as conn_module
        conn_module._default_manager = None
        
        with pytest.raises(DatabaseError):
            conn_module.get_manager()
    
    def test_init_returns_manager(self, tmp_path):
        """Test that init returns a ConnectionManager"""
        from src.database.connection import init
        manager = init(tmp_path / "test.db")
        assert isinstance(manager, ConnectionManager)
    
    def test_get_manager_returns_same_instance(self, tmp_path):
        """Test singleton behavior"""
        from src.database.connection import init, get_manager
        init(tmp_path / "test.db")
        
        manager1 = get_manager()
        manager2 = get_manager()
        assert manager1 is manager2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])