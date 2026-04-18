import pytest
import tempfile
from pathlib import Path
import pandas as pd
import io
import json
import uuid
from datetime import datetime

from src.api.app import create_app
from src.database import connection as db
from src.database.schema import SchemaManager

@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = create_app({
        'TESTING': True,
        'MAX_CONTENT_LENGTH': 50 * 1024 * 1024,
        'UPLOAD_FOLDER': tempfile.gettempdir()
    })
    yield app


@pytest.fixture
def sample_csv_bytes():
    """Create sample CSV file as bytes."""
    content = """id,name,email,age,score
1,Alice,alice@example.com,25,95.5
2,Bob,bob@example.com,30,87.0
3,Charlie,charlie@example.com,35,92.3
4,David,david@example.com,40,78.9
5,Eve,eve@example.com,45,99.1"""
    return content.encode('utf-8')


@pytest.fixture
def sample_tsv_bytes():
    """Create sample TSV file as bytes."""
    content = """product\tquantity\tprice
Widget\t10\t9.99
Gadget\t20\t19.99
Doohickey\t30\t29.99"""
    return content.encode('utf-8')


@pytest.fixture
def sample_xlsx_bytes():
    """Create sample XLSX file as bytes."""
    df = pd.DataFrame({
        'department': ['Sales', 'Engineering', 'Marketing', 'HR'],
        'headcount': [15, 50, 10, 8],
        'budget': [100000, 500000, 75000, 50000]
    })
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    output.seek(0)
    return output.read()


@pytest.fixture
def multi_sheet_xlsx_bytes():
    """Create multi-sheet XLSX file as bytes."""
    df1 = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
    df2 = pd.DataFrame({'x': [10, 20], 'y': [30, 40]})
    df3 = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Sheet1', index=False)
        df2.to_excel(writer, sheet_name='Data', index=False)
        df3.to_excel(writer, sheet_name='People', index=False)
    output.seek(0)
    return output.read()


@pytest.fixture
def empty_csv_bytes():
    """Create empty CSV file as bytes."""
    return b""


@pytest.fixture
def invalid_csv_bytes():
    """Create invalid CSV file as bytes."""
    return b"not,a,valid\ncsv,file,format\nwith,inconsistent\ncolumns"


@pytest.fixture
def csv_with_nulls_bytes():
    """Create CSV with null values as bytes."""
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'value1': [10, None, 30, None, 50],
        'value2': ['a', 'b', None, 'd', None]
    })
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode('utf-8')


@pytest.fixture
def large_csv_bytes():
    """Create a larger CSV file as bytes."""
    rows = ["id,name,value,category,score"]
    for i in range(1000):
        rows.append(f"{i},name_{i},{i * 1.5},cat_{i % 10},{i % 100}")
    content = "\n".join(rows)
    return content.encode('utf-8')


@pytest.fixture
def csv_with_unicode_bytes():
    """Create CSV with unicode characters as bytes."""
    content = """name,city,country
José,São Paulo,Brasil
François,Montréal,Canada
李明,北京,中国
山田太郎,東京,日本"""
    return content.encode('utf-8')

@pytest.fixture
def app_with_db(tmp_path):
    """Create app with test database."""
    db_path = tmp_path / "test.db"
    
    # Create app - this now initializes schema too (with Option 1 or 2 above)
    app = create_app({
        'TESTING': True,
        'DATABASE_PATH': str(db_path),
    })
    
    yield app
    
    # Cleanup
    db.close_manager()

@pytest.fixture
def app_with_db(tmp_path):
    """Create app with test database."""
    db_path = tmp_path / "test.db"
    
    app = create_app({
        'TESTING': True,
        'DATABASE_PATH': str(db_path),
    })
    
    yield app
    
    # Cleanup
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


# Repository fixtures - use actual application code
@pytest.fixture
def receipt_repository(app_with_db):
    """Get receipt repository."""
    from src.database.repositories.receipts import ReceiptRepository
    with app_with_db.app_context():
        return ReceiptRepository()


@pytest.fixture
def category_repository(app_with_db):
    """Get category repository."""
    from src.database.repositories.categories import CategoryRepository
    with app_with_db.app_context():
        return CategoryRepository()

@pytest.fixture
def db_conn(app_with_db):
    """Get database connection within app context."""
    with app_with_db.app_context():
        yield db.get_db()


class TestDataFactory:
    """Factory for creating test data with auto-generated unique values."""
    
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
        }
        defaults.update(kwargs)
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    '''INSERT INTO receipts (
                        original_filename, stored_filename, file_path,
                        vendor, date, amount, confidence, 
                        selected_method, raw_text, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
    def create_upload(app, filename=None):
        """Insert a test upload."""
        unique_id = TestDataFactory._unique_id()
        filename = filename or f'upload_{unique_id}.csv'
        
        with app.app_context():
            manager = db.get_manager()
            with manager.transaction() as conn:
                cursor = conn.execute(
                    'INSERT INTO uploads (filename) VALUES (?)',
                    (filename,)
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


@pytest.fixture
def test_data():
    """Provide test data factory."""
    return TestDataFactory()


@pytest.fixture
def test_hierarchy(app_with_db, test_data):
    """Create a full test hierarchy and return IDs."""
    return test_data.create_full_hierarchy(app_with_db)