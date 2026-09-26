import pytest

@pytest.fixture(autouse=True)
def _db(app_with_db):
    yield