import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    manager = Mock()
    
    # Mock transaction context manager
    transaction_context = Mock()
    transaction_context.__enter__ = Mock(return_value=Mock())
    transaction_context.__exit__ = Mock(return_value=False)
    manager.transaction.return_value = transaction_context
    
    # Mock connection context manager
    connection_context = Mock()
    connection_context.__enter__ = Mock(return_value=Mock())
    connection_context.__exit__ = Mock(return_value=False)
    manager.get_connection.return_value = connection_context
    
    return manager


@pytest.fixture
def mock_cursor():
    """Create a mock cursor."""
    cursor = Mock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.lastrowid = 1
    cursor.rowcount = 1
    return cursor