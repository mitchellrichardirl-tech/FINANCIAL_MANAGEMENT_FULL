import pytest

from src.database import connection as db


@pytest.fixture
def db_manager(app_with_db):
    """The app's connection manager, for setup/verification SQL.

    Repository tests run against the fixtures in tests/conftest.py, so this
    shadows the standalone manager in tests/test_database/conftest.py (which
    builds its own schema on a separate file) to avoid two managers fighting
    over the module-level global.
    """
    with app_with_db.app_context():
        yield db.get_manager()