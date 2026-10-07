import pytest
from src.database.connection import ConnectionManager
from src.database.connection import init as init_connection
from src.database.migrations import migrate
from src.database.schema import initialize_schema


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path"""
    return tmp_path / "test.db"


@pytest.fixture
def db_manager(temp_db_path):
    """Create and initialize connection manager"""
    manager = ConnectionManager(temp_db_path)
    init_connection(temp_db_path)
    initialize_schema(manager)
    migrate(temp_db_path)
    return manager
