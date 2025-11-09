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

# # Register Receipt class for proper mocking
# @pytest.fixture(autouse=True)
# def setup_receipt_mock():
#     """Setup Receipt class for mocking."""
#     with patch('src.receipts.receipt_loader.Receipt') as mock:
#         # Make Receipt callable return a mock instance
#         mock_instance = Mock()
#         mock.return_value = mock_instance
#         mock_instance.source_file = None
#         mock_instance.page_number = None
#         mock_instance.original_image = None
#         mock_instance.processed_image = None
#         yield