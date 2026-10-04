# tests/test_meta/test_conventions.py
import re
from pathlib import Path

TESTS_DIR = Path(__file__).parent.parent
ALLOWED = {
    'conftest.py',  # build_test_db lives here,
    'test_migrations_receipt_links.py', # Need to test before and after migrations,
    'test_schema.py',
    'test_conventions.py',
}

def test_no_direct_initialize_schema_in_tests():
    """Tests must build databases via app_with_db (schema + migrations).
    A bare initialize_schema() produces an unmigrated schema that cannot
    exist in production."""
    offenders = []
    for path in TESTS_DIR.rglob('*.py'):
        if path.name in ALLOWED:
            continue
        if re.search(r'\binitialize_schema\s*\(', path.read_text()):
            offenders.append(str(path.relative_to(TESTS_DIR)))
    assert offenders == [], f"Use app_with_db instead of initialize_schema: {offenders}"