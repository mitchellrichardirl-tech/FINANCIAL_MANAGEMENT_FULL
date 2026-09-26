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