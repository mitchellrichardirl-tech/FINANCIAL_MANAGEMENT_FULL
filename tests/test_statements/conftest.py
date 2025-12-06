import pytest
import pandas as pd
from io import BytesIO
from flask import Flask

@pytest.fixture
def sample_dataframe():
    """Sample DataFrame for testing."""
    return pd.DataFrame({
        'name': ['John', 'Jane', 'Bob'],
        'amount': [100, 200, 300],
        'date': ['2024-01-15', '2024-01-16', '2024-01-17']
    })


@pytest.fixture
def create_csv_bytes():
    """Factory fixture to create CSV content as bytes."""
    def _create_csv(data: dict, encoding='utf-8'):
        df = pd.DataFrame(data)
        return df.to_csv(index=False).encode(encoding)
    return _create_csv


@pytest.fixture
def create_excel_bytes():
    """Factory fixture to create Excel content as bytes."""
    def _create_excel(data: dict, engine='openpyxl'):
        df = pd.DataFrame(data)
        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine=engine)
        buffer.seek(0)
        return buffer.getvalue()
    return _create_excel

@pytest.fixture
def app():
    """Create a Flask application for testing."""
    app = Flask(__name__)
    app.config['MAX_FILE_SIZE'] = 10 * 1024 * 1024  # 10 MB
    return app


@pytest.fixture
def mock_flask_app(app):
    """Provide Flask app context for tests."""
    with app.app_context():
        yield app