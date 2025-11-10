# Add to conftest.py
import pytest
from unittest.mock import Mock, patch

from src.models.receipt import Receipt
from src.models.processing_config import ProcessingConfig

@pytest.fixture
def mock_receipt():
    """Create a mock Receipt object."""
    receipt = Mock(spec=Receipt)
    return receipt

@pytest.fixture
def mock_processing_config_instance():
    """Create a mock ProcessingConfig instance."""
    config = Mock(spec=ProcessingConfig)
    return config

# Disable logging for receipt extractor tests as well
@pytest.fixture(autouse=True)
def disable_receipt_extractor_logging():
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)

# Register custom markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )