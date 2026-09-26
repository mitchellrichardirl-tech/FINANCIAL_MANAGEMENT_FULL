import pytest
import sys
from pathlib import Path
import uuid
import logging
from typing import Union
import shutil

import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.app import create_app
from src.database import connection as db

@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    """Build the schema once per test session."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    app = create_app({'TESTING': True, 'DATABASE_PATH': str(path)})
    db.close_manager()   # release the global; we only wanted the file
    return path

@pytest.fixture
def app_with_db(tmp_path, _template_db):
    """Fresh DB per test, copied from the pre-built template."""
    db_path = tmp_path / "test.db"
    shutil.copy(_template_db, db_path)
    app = create_app({
        'TESTING': True,
        'DATABASE_PATH': str(db_path),
    })
    yield app
    db.close_manager()

@pytest.fixture
def client(app_with_db):
    """Get test client."""
    return app_with_db.test_client()

@pytest.fixture
def db_manager(app_with_db):
    """Get database manager within app context."""
    with app_with_db.app_context():
        yield db.get_manager()

@pytest.fixture
def db_conn(app_with_db):
    """Get database connection within app context."""
    with app_with_db.app_context():
        yield db.get_db()


class TestDataFactory:
    """Factory for creating test data with auto-generated unique values."""
    __test__ = False

    @staticmethod
    def _unique_id():
        """Generate a unique identifier."""
        return uuid.uuid4().hex[:8]
    
    @staticmethod
    def create_receipt(app, **kwargs):
        """Insert a test receipt."""
        unique_id = TestDataFactory._unique_id()
        
        defaults = {
            'original_filename': f'test_receipt_{unique_id}.jpg',
            'stored_filename': f'stored_{unique_id}.jpg',
            'file_path': f'/tmp/receipts/{unique_id}.jpg',
            'vendor': 'Test Store',
            'date': '2024-01-15',
            'amount': 10.00,
            'confidence': 2,
            'selected_method': 'ocr',
            'raw_text': 'Test receipt text',
            'metadata': '{}',
            'status': 'pending',
            'confirmed_at': None,
        }
        defaults.update(kwargs)
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO receipts (
                        original_filename, stored_filename, file_path,
                        vendor, date, amount, confidence, 
                        selected_method, raw_text, metadata, status,
                        confirmed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        defaults['original_filename'],
                        defaults['stored_filename'],
                        defaults['file_path'],
                        defaults['vendor'],
                        defaults['date'],
                        defaults['amount'],
                        defaults['confidence'],
                        defaults['selected_method'],
                        defaults['raw_text'],
                        defaults['metadata'],
                        defaults['status'],
                        defaults['confirmed_at'],
                    )
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_category(app, category=None, description=None):
        """Insert a test category."""
        unique_id = TestDataFactory._unique_id()
        category = category or f'Category_{unique_id}'
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    'INSERT INTO categories (category, description) VALUES (?, ?)',
                    (category, description)
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_subcategory(app, category_id, sub_category=None, description=None):
        """Insert a test sub-category."""
        unique_id = TestDataFactory._unique_id()
        sub_category = sub_category or f'SubCategory_{unique_id}'
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO sub_categories (sub_category, description, category_id) 
                       VALUES (?, ?, ?)''',
                    (sub_category, description, category_id)
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_type(app, sub_category_id, type_name=None, description=None):
        """Insert a test type."""
        unique_id = TestDataFactory._unique_id()
        type_name = type_name or f'Type_{unique_id}'
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO types (type, description, sub_category_id) 
                       VALUES (?, ?, ?)''',
                    (type_name, description, sub_category_id)
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_party(app, type_id, name=None, description=None):
        """Insert a test party."""
        unique_id = TestDataFactory._unique_id()
        name = name or f'Party_{unique_id}'
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO parties (name, description, type_id) 
                       VALUES (?, ?, ?)''',
                    (name, description, type_id)
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_upload(app, filename=None, original_filename=None, file_type='csv'):
        """Insert a test upload."""
        unique_id = TestDataFactory._unique_id()
        filename = filename or f'upload_{unique_id}.csv'
        original_filename = original_filename or filename
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO uploads (original_filename, filename, file_type)
                       VALUES (?, ?, ?)''',
                    (original_filename, filename, file_type)
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_transaction(app, upload_id, party_id, **kwargs):
        """Insert a test transaction."""
        defaults = {
            'transaction_date': '2024-01-15',
            'amount': 100.00,
            'description': 'Test transaction',
            'cleaned_description': 'Test transaction',
            'is_credit': 0,
            'is_kids': 0,
            'is_one_off': 0,
            'account_id': None,
            'receipt_id': None,
        }
        defaults.update(kwargs)
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO transactions (
                        transaction_date, amount, description, cleaned_description,
                        is_credit, is_kids, is_one_off, account_id,
                        upload_id, party_id, receipt_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        defaults['transaction_date'],
                        defaults['amount'],
                        defaults['description'],
                        defaults['cleaned_description'],
                        defaults['is_credit'],
                        defaults['is_kids'],
                        defaults['is_one_off'],
                        defaults['account_id'],
                        upload_id,
                        party_id,
                        defaults['receipt_id'],
                    )
                )
                return cursor.lastrowid
    
    @staticmethod
    def create_full_hierarchy(app):
        """
        Create a complete category hierarchy for testing.
        
        Returns:
            dict with 'category_id', 'subcategory_id', 'type_id', 'party_id'
        """
        category_id = TestDataFactory.create_category(app, 'Test Category')
        subcategory_id = TestDataFactory.create_subcategory(
            app, category_id, 'Test SubCategory'
        )
        type_id = TestDataFactory.create_type(
            app, subcategory_id, 'Test Type'
        )
        party_id = TestDataFactory.create_party(
            app, type_id, 'Test Party'
        )
        
        return {
            'category_id': category_id,
            'subcategory_id': subcategory_id,
            'type_id': type_id,
            'party_id': party_id,
        }

    @staticmethod
    def soft_delete_transaction(app, transaction_id, reason='user'):
        """Mark a transaction as soft-deleted."""
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                conn.execute(
                    "UPDATE transactions SET deleted_at = strftime('%Y-%m-%d %H:%M:%f','now'), "
                    "deleted_reason = ? WHERE id = ?",
                    (reason, transaction_id),
                )
    @staticmethod
    def set_receipt_status(app, receipt_id, status, confirmed_at=None):
        """Directly set receipt status (bypasses service — for fixtures only)."""
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                conn.execute(
                    "UPDATE receipts SET status = ?, confirmed_at = ? WHERE id = ?",
                    (status, confirmed_at, receipt_id),
                )
    @staticmethod
    def fetch_one(app, sql, params=()):
        with app.app_context():
            manager = db.get_manager()
            with manager.get_connection() as conn:
                row = conn.execute(sql, params).fetchone()
                return dict(row) if row is not None else None


@pytest.fixture
def test_data():
    """Provide test data factory."""
    return TestDataFactory()

@pytest.fixture
def test_hierarchy(app_with_db, test_data):
    """Create a full test hierarchy and return IDs."""
    return test_data.create_full_hierarchy(app_with_db)

@pytest.fixture
def make_transaction(app_with_db, test_data, test_hierarchy):
    """Factory fixture: make_transaction(**overrides) -> transaction id."""
    upload_id = test_data.create_upload(app_with_db)
    def _make(**kwargs):
        kwargs.setdefault('amount', -10.00)
        return test_data.create_transaction(
            app_with_db, upload_id, test_hierarchy['party_id'], **kwargs
        )
    return _make

@pytest.fixture
def live_transaction(app_with_db, test_data, test_hierarchy):
    """A single live, unlinked transaction. Returns its id."""
    upload_id = test_data.create_upload(app_with_db)
    return test_data.create_transaction(
        app_with_db, upload_id, test_hierarchy['party_id'],
        transaction_date='2024-01-15', amount=-10.00,
    )

@pytest.fixture
def unlinked(app_with_db, test_data):
    return test_data.create_receipt(
        app_with_db,
        status="unlinked",
        vendor="Tesco",
        date="2024-01-15",
        amount=23.40,
        confirmed_at="2024-01-16 10:00:00.000",
    )

@pytest.fixture
def unwrap():
    def _unwrap(response):
        body = response.get_json()
        if body:
            if 'error' in body:
                return body['error']
            if 'success' in body:
                if 'extracted_data' in body:
                    return body
                elif 'data' in body:
                    return body['data']
            raise KeyError(f'Neither "success" nor "error" in json body. Keys are {",".join(list(body.keys()))}')
        raise ValueError(f'Response does not return json. Type: {type(response)}')
    return _unwrap
