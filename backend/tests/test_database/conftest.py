import pytest

from src.database.connection import ConnectionManager, init as init_connection
from src.database.schema import initialize_schema
from src.database.migrations import migrate

@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path"""
    return tmp_path / "test.db"


@pytest.fixture
def connection_manager(temp_db_path):
    """Create and initialize connection manager"""
    manager = ConnectionManager(temp_db_path)
    init_connection(temp_db_path)
    initialize_schema(manager)
    migrate(temp_db_path)
    return manager