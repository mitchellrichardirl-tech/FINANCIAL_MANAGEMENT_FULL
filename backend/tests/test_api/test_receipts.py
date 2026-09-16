import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import io
from io import BytesIO
from flask import Flask

from pathlib import Path
import numpy as np

# Import your app and database
from src.api.app import create_app
from src.api.routes.receipts import receipt_repository as rm, receipt_loader, receipt_extractor
from src.models.receipt import Receipt
from src.database.connection import ConnectionManager, DatabaseError, init as init_connection
from src.database import connection as db

@pytest.fixture
def client():
    """Create a test client"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing"""
    # Create a minimal valid JPEG header
    jpeg_header = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00, 0xFF, 0xD9
    ])
    return BytesIO(jpeg_header)


@pytest.fixture
def sample_pdf_file():
    """Create a sample PDF file for testing"""
    # Minimal PDF header
    pdf_content = b'%PDF-1.4\n%EOF'
    return BytesIO(pdf_content)


@pytest.fixture
def mock_image():
    """Create a mock numpy image array"""
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def sample_receipt(mock_image):
    """Create a sample processed receipt"""
    receipt = Receipt(
        original_filename=Path('test_receipt.jpg'),
        page_number=1,
        original_image=mock_image,
        processed_images={
            'original': mock_image,
            'enhanced': mock_image,
            'grayscale': mock_image
        },
        stored_filename='20240115_123045_abc123.jpg',
        file_path=Path('/tmp/20240115_123045_abc123.jpg')
    )
    receipt.vendor = 'Walmart'
    receipt.amount = 45.67
    receipt.date = datetime(2024, 1, 15)
    receipt.confidence = 3
    receipt.selected_method = 'enhanced'
    receipt.extracted_text = 'WALMART\nStore #1234\nTOTAL: $45.67'
    return receipt


@pytest.fixture
def low_confidence_receipt(mock_image):
    """Create a receipt with low confidence"""
    receipt = Receipt(
        original_filename=Path('unclear_receipt.jpg'),
        page_number=1,
        original_image=mock_image,
        processed_images={
            'original': mock_image,
            'grayscale': mock_image
        },
        stored_filename='20240115_143022_def456.jpg',
        file_path=Path('/tmp/20240115_143022_def456.jpg')
    )
    receipt.vendor = None
    receipt.amount = 25.00
    receipt.date = None
    receipt.confidence = 1
    receipt.selected_method = 'grayscale'
    receipt.extracted_text = 'Some unclear text\n25.00'
    return receipt


@pytest.fixture
def sample_receipts():
    """Sample receipt data for testing"""
    return [
        {
            'id': 1,
            'original_filename': 'receipt_001.jpg',
            'stored_filename': '20240115_123045_abc123.jpg',
            'file_path': '/uploads/20240115_123045_abc123.jpg',
            'vendor': 'Walmart',
            'amount': 45.67,
            'date': datetime(2024, 1, 15),
            'confidence': 3,
            'selected_method': 'tesseract',
            'raw_text': 'WALMART...',
            'metadata': {'processing_time': 1.2},
            'created_at': '2024-01-15 12:30:45.123',
            'updated_at': '2024-01-15 12:30:45.123'
        },
        {
            'id': 2,
            'original_filename': 'receipt_002.jpg',
            'stored_filename': '20240116_143022_def456.jpg',
            'file_path': '/uploads/20240116_143022_def456.jpg',
            'vendor': 'Target',
            'amount': 123.45,
            'date': datetime(2024, 1, 16),
            'confidence': 2,
            'selected_method': 'easyocr',
            'raw_text': 'TARGET...',
            'metadata': {'processing_time': 2.1},
            'created_at': '2024-01-16 14:30:22.456',
            'updated_at': '2024-01-16 14:30:22.456'
        },
        {
            'id': 3,
            'original_filename': 'receipt_003.jpg',
            'stored_filename': '20240117_091533_ghi789.jpg',
            'file_path': '/uploads/20240117_091533_ghi789.jpg',
            'vendor': 'Walmart',
            'amount': 89.99,
            'date': datetime(2024, 1, 17),
            'confidence': 1,
            'selected_method': 'tesseract',
            'raw_text': 'WALMART...',
            'metadata': {'processing_time': 0.9},
            'created_at': '2024-01-17 09:15:33.789',
            'updated_at': '2024-01-17 09:15:33.789'
        }
    ]


class TestProcessReceiptEndpoint:
    """Tests for POST /api/receipts/process endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_success_single_image(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test successful processing of a single receipt image"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['original_filename'] == 'receipt.jpg'
        assert data['page_count'] == 1
        assert data['extracted_data']['vendor'] == 'Walmart'
        assert data['extracted_data']['amount'] == 45.67
        assert data['extracted_data']['date'] == '2024-01-15T00:00:00'
        assert data['extracted_data']['confidence'] == 3
        assert data['extracted_data']['selected_method'] == 'enhanced'
        assert 'WALMART' in data['extracted_data']['raw_text']
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_success_png(
        self, mock_process_files, mock_extract, client, sample_receipt
    ):
        """Test successful processing of PNG file"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        png_file = BytesIO(b'\x89PNG\r\n\x1a\n')
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (png_file, 'receipt.png')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['original_filename'] == 'receipt.png'
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_success_pdf_single_page(
        self, mock_process_files, mock_extract, client, sample_pdf_file, sample_receipt
    ):
        """Test successful processing of single-page PDF"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_pdf_file, 'receipt.pdf')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['original_filename'] == 'receipt.pdf'
        assert data['page_count'] == 1
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_success_multipage_pdf(
        self, mock_process_files, mock_extract, client, sample_pdf_file, 
        sample_receipt, low_confidence_receipt
    ):
        """Test successful processing of multi-page PDF"""
        # Create two different receipts for two pages
        page1_receipt = low_confidence_receipt  # confidence 1
        page2_receipt = sample_receipt  # confidence 3
        
        mock_process_files.return_value = [page1_receipt, page2_receipt]
        mock_extract.side_effect = [page1_receipt, page2_receipt]
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_pdf_file, 'multi_receipt.pdf')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['page_count'] == 2
        assert 'all_pages' in data
        assert len(data['all_pages']) == 2
        
        # Best result should be page2 (higher confidence)
        assert data['extracted_data']['confidence'] == 3
        assert data['extracted_data']['vendor'] == 'Walmart'
        assert data['best_page_index'] == 1
        
        # Check all pages are included
        assert data['all_pages'][0]['confidence'] == 1
        assert data['all_pages'][1]['confidence'] == 3
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_null_values(
        self, mock_process_files, mock_extract, client, sample_image_file, mock_image
    ):
        """Test processing when OCR extracts null values"""
        receipt = Receipt(
            original_filename=Path('blank_receipt.jpg'),
            page_number=1,
            original_image=mock_image,
            processed_images={'original': mock_image},
            stored_filename='stored.jpg',
            file_path=Path('/tmp/stored.jpg')
        )
        receipt.vendor = None
        receipt.amount = None
        receipt.date = None
        receipt.confidence = 0
        receipt.selected_method = 'enhanced'
        receipt.extracted_text = ''
        
        mock_process_files.return_value = [receipt]
        mock_extract.return_value = receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'blank.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert data['extracted_data']['vendor'] is None
        assert data['extracted_data']['amount'] is None
        assert data['extracted_data']['date'] is None
        assert data['extracted_data']['confidence'] == 0
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_partial_extraction(
        self, mock_process_files, mock_extract, client, sample_image_file, mock_image
    ):
        """Test processing with partial data extraction"""
        receipt = Receipt(
            original_filename=Path('partial_receipt.jpg'),
            page_number=1,
            original_image=mock_image,
            processed_images={'original': mock_image},
            stored_filename='stored.jpg',
            file_path=Path('/tmp/stored.jpg')
        )
        receipt.vendor = 'Target'
        receipt.amount = None  # Amount not extracted
        receipt.date = datetime(2024, 1, 20)
        receipt.confidence = 2
        receipt.selected_method = 'grayscale'
        receipt.extracted_text = 'TARGET\nDate: 01/20/2024'
        
        mock_process_files.return_value = [receipt]
        mock_extract.return_value = receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'partial.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['extracted_data']['vendor'] == 'Target'
        assert data['extracted_data']['amount'] is None
        assert data['extracted_data']['date'] is not None
        assert data['extracted_data']['confidence'] == 2
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_uppercase_extension(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test file with uppercase extension"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.JPG')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_jpeg_extension(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test JPEG extension (not just JPG)"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpeg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_special_characters_in_filename(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test filename with special characters gets sanitized"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, '../../../etc/passwd.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        # Filename should be sanitized
        assert '/' not in data['original_filename']
        assert '..' not in data['original_filename']
    
    # ========== Validation Error Cases ==========
    
    def test_process_receipt_no_file_field(self, client):
        """Test error when no file field is provided"""
        response = client.post(
            '/api/receipts/process',
            data={},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data
        assert 'file is required' in data['error']['message']
    
    def test_process_receipt_empty_file_field(self, client):
        """Test error when file field is empty"""
        response = client.post(
            '/api/receipts/process',
            data={'file': (BytesIO(b''), '')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data
        assert 'No file' in data['error']['message']
    
    def test_process_receipt_invalid_file_type_doc(self, client):
        """Test error when file type is not allowed (doc)"""
        response = client.post(
            '/api/receipts/process',
            data={'file': (BytesIO(b'text content'), 'receipt.doc')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data
        assert 'Invalid file type' in data['error']['message']
        assert 'Allowed types' in data['error']['message']
    
    def test_process_receipt_invalid_file_type_gif(self, client):
        """Test error when file type is not allowed (gif)"""
        response = client.post(
            '/api/receipts/process',
            data={'file': (BytesIO(b'GIF89a'), 'receipt.gif')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'Invalid file type' in data['error']['message']
    
    def test_process_receipt_no_extension(self, client):
        """Test error when file has no extension"""
        response = client.post(
            '/api/receipts/process',
            data={'file': (BytesIO(b'content'), 'receipt')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert ['file type'] in data['error']['message']
    
    # ========== Processing Error Cases ==========
    
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_loader_returns_empty(
        self, mock_process_files, client, sample_image_file
    ):
        """Test error when loader returns no receipts"""
        mock_process_files.return_value = []
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 422
        assert 'error' in data
        assert 'Unable to process' in data['error']['message']
    
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_loader_throws_file_not_found(
        self, mock_process_files, client, sample_image_file
    ):
        """Test error when loader throws FileNotFoundError"""
        mock_process_files.side_effect = FileNotFoundError("File not found")
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'error' in data
        assert 'File processing failed' in data['error']['message']
    
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_loader_throws_value_error(
        self, mock_process_files, client, sample_image_file
    ):
        """Test error when loader throws ValueError"""
        mock_process_files.side_effect = ValueError("Invalid image format")
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 422
        assert 'error' in data
        assert 'Processing failed' in data['error']['message']
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_extractor_throws_exception(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test error when extractor throws exception"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.side_effect = Exception("OCR engine failed")
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data
        assert 'Internal server error' in data['error']
    
    # ========== Response Format Tests ==========
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_response_structure_single(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test response structure for single image"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        # Check required fields
        assert 'success' in data
        assert 'original_filename' in data
        assert 'extracted_data' in data
        assert 'page_count' in data
        
        # Check extracted_data structure
        extracted = data['extracted_data']
        assert 'vendor' in extracted
        assert 'amount' in extracted
        assert 'date' in extracted
        assert 'confidence' in extracted
        assert 'selected_method' in extracted
        assert 'raw_text' in extracted
        
        # Should NOT have multi-page fields
        assert 'all_pages' not in data
        assert 'best_page_index' not in data
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_process_receipt_content_type(
        self, mock_process_files, mock_extract, client, sample_image_file, sample_receipt
    ):
        """Test that response has correct content type"""
        mock_process_files.return_value = [sample_receipt]
        mock_extract.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/process',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        
        assert response.content_type == 'application/json'
    
    # ========== HTTP Method Tests ==========
    
    def test_process_receipt_wrong_method_get(self, client):
        """Test that GET method is not allowed"""
        response = client.get('/api/receipts/process')
        
        assert response.status_code == 405  # Method Not Allowed

class TestGetReceiptEndpoint:
    """Tests for GET /api/receipts/<receipt_id> endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_success(self, mock_get_by_id, client, sample_receipts):
        """Test successfully retrieving a receipt by ID"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'data' in data
        assert 'receipt' in data['data']
        assert data['data']['receipt']['id'] == 1
        assert data['data']['receipt']['vendor'] == 'Walmart'
        assert data['data']['receipt']['amount'] == 45.67
        
        mock_get_by_id.assert_called_once_with(1)
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_response_format(self, mock_get_by_id, client, sample_receipts):
        """Test response has correct structure"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        receipt = data['data']['receipt']
        
        # Check all expected fields
        assert 'id' in receipt
        assert 'original_filename' in receipt
        assert 'stored_filename' in receipt
        assert 'vendor' in receipt
        assert 'amount' in receipt
        assert 'date' in receipt
        assert 'confidence' in receipt
        assert 'selected_method' in receipt
        assert 'created_at' in receipt
        assert 'updated_at' in receipt
        
        # file_path should not be exposed
        assert 'file_path' not in receipt
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_date_formatted(self, mock_get_by_id, client, sample_receipts):
        """Test date is properly formatted in response"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        assert data['data']['receipt']['date'] == '2024-01-15T00:00:00'
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_with_null_date(self, mock_get_by_id, client):
        """Test handling receipt with null date"""
        receipt = {
            'id': 1,
            'original_filename': 'receipt.jpg',
            'stored_filename': 'stored.jpg',
            'vendor': 'Store',
            'amount': 10.00,
            'date': None,
            'confidence': 1,
            'selected_method': 'tesseract',
            'raw_text': None,
            'metadata': {},
            'created_at': '2024-01-15 12:00:00',
            'updated_at': '2024-01-15 12:00:00'
        }
        mock_get_by_id.return_value = receipt
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['receipt']['date'] is None
    
    # ========== Not Found Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_not_found(self, mock_get_by_id, client):
        """Test error when receipt does not exist"""
        mock_get_by_id.return_value = None
        
        response = client.get('/api/receipts/999')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'error' in data
        assert '999' in data['error']
        assert 'not found' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_zero_id(self, mock_get_by_id, client):
        """Test with receipt ID of 0"""
        mock_get_by_id.return_value = None
        
        response = client.get('/api/receipts/0')
        data = json.loads(response.data)
        
        assert response.status_code == 404
    
    # ========== Error Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_database_error(self, mock_get_by_id, client):
        """Test handling database errors"""
        mock_get_by_id.side_effect = DatabaseError("Connection failed")
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data
        assert 'Database error' in data['error']
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_unexpected_error(self, mock_get_by_id, client):
        """Test handling unexpected exceptions"""
        mock_get_by_id.side_effect = Exception("Unexpected error")
        
        response = client.get('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'error' in data
        assert 'Internal server error' in data['error']
    
    # ========== Edge Cases ==========
    
    def test_get_receipt_invalid_id_string(self, client):
        """Test with non-integer ID"""
        response = client.get('/api/receipts/abc')
        
        assert response.status_code == 404  # Flask returns 404 for invalid int
    
    def test_get_receipt_negative_id(self, client):
        """Test with negative ID"""
        response = client.get('/api/receipts/-1')
        
        assert response.status_code == 404
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_large_id(self, mock_get_by_id, client):
        """Test with very large ID"""
        mock_get_by_id.return_value = None
        
        response = client.get('/api/receipts/999999999')
        data = json.loads(response.data)
        
        assert response.status_code == 404
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_content_type(self, mock_get_by_id, client, sample_receipts):
        """Test response content type"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.get('/api/receipts/1')
        
        assert response.content_type == 'application/json'


class TestUpdateReceiptEndpoint:
    """Tests for PUT /api/receipts/<receipt_id> endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_vendor(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating vendor field"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'vendor': 'New Vendor'}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'vendor': 'New Vendor'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['receipt']['vendor'] == 'New Vendor'
        mock_update.assert_called_once()
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_amount(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating amount field"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'amount': 99.99}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'amount': 99.99}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['receipt']['amount'] == 99.99
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_date(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating date field"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'date': datetime(2024, 2, 20)}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'date': '2024-02-20'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        mock_update.assert_called_once()
        # Verify date was parsed and passed to update
        call_kwargs = mock_update.call_args.kwargs
        assert 'date' in call_kwargs
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_confidence(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating confidence field"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'confidence': 2}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': 2}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['receipt']['confidence'] == 2
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_multiple_fields(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating multiple fields at once"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'vendor': 'New Store', 'amount': 150.00}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({
                'vendor': 'New Store',
                'amount': 150.00,
                'date': '2024-03-15'
            }),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'message' in data['data']
        assert 'updated' in data['data']['message'].lower()
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_set_null_values(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test setting fields to null"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'vendor': None, 'amount': None}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'vendor': None, 'amount': None}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_raw_text(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test updating raw_text field"""
        mock_get_by_id.return_value = sample_receipts[0]
        updated = {**sample_receipts[0], 'raw_text': 'Updated raw text'}
        mock_update.return_value = updated
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'raw_text': 'Updated raw text'}),
            content_type='application/json'
        )
        
        assert response.status_code == 200
    
    # ========== Validation Error Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_not_found(self, mock_get_by_id, client):
        """Test error when receipt does not exist"""
        mock_get_by_id.return_value = None
        
        response = client.put(
            '/api/receipts/999',
            data=json.dumps({'vendor': 'New Vendor'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_no_json_body(self, mock_get_by_id, client, sample_receipts):
        """Test error when no JSON body provided"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'JSON' in data['error']
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_json(self, mock_get_by_id, client, sample_receipts):
        """Test error with malformed JSON"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data='not valid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_empty_body(self, mock_get_by_id, client, sample_receipts):
        """Test error when no fields to update"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'No valid fields' in data['error']
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_amount_string(self, mock_get_by_id, client, sample_receipts):
        """Test error with non-numeric amount"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'amount': 'not-a-number'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'amount' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_date_format(self, mock_get_by_id, client, sample_receipts):
        """Test error with invalid date format"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'date': '01-15-2024'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'date' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_confidence_negative(self, mock_get_by_id, client, sample_receipts):
        """Test error with negative confidence"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': -1}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'confidence' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_confidence_too_high(self, mock_get_by_id, client, sample_receipts):
        """Test error with confidence > 3"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': 5}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'confidence' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_invalid_confidence_float(self, mock_get_by_id, client, sample_receipts):
        """Test error with float confidence"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': 2.5}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
    
    # ========== Database Error Cases ==========
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_database_error(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test handling database errors"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_update.side_effect = DatabaseError("Update failed")
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'vendor': 'New Vendor'}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']
    
    # ========== Edge Cases ==========
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_unknown_fields_ignored(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test that unknown fields are ignored"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_update.return_value = sample_receipts[0]
        
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({
                'vendor': 'New Vendor',
                'unknown_field': 'ignored'
            }),
            content_type='application/json'
        )
        
        assert response.status_code == 200
    
    @patch.object(rm, 'update')
    @patch.object(rm, 'get_by_id')
    def test_update_receipt_confidence_boundaries(self, mock_get_by_id, mock_update, client, sample_receipts):
        """Test confidence at valid boundaries"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_update.return_value = {**sample_receipts[0], 'confidence': 0}
        
        # Test confidence 0
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': 0}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        # Test confidence 3
        mock_update.return_value = {**sample_receipts[0], 'confidence': 3}
        response = client.put(
            '/api/receipts/1',
            data=json.dumps({'confidence': 3}),
            content_type='application/json'
        )
        assert response.status_code == 200


class TestDeleteReceiptEndpoint:
    """Tests for DELETE /api/receipts/<receipt_id> endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'delete')
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_success(self, mock_get_by_id, mock_delete, client, sample_receipts):
        """Test successfully deleting a receipt"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_delete.return_value = True
        
        response = client.delete('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'deleted' in data['data']['message'].lower()
        assert data['data']['deleted_id'] == 1
        
        mock_delete.assert_called_once_with(1)
    
    @patch('os.path.exists', return_value=True)
    @patch('pathlib.Path.unlink')
    @patch.object(rm, 'delete')
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_with_file(self, mock_get_by_id, mock_delete, mock_unlink, mock_exists, client, sample_receipts):
        """Test deleting receipt also deletes the file"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_delete.return_value = True
        
        response = client.delete('/api/receipts/1')
        
        assert response.status_code == 200
    
    @patch.object(rm, 'delete')
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_without_file_path(self, mock_get_by_id, mock_delete, client):
        """Test deleting receipt when file_path is None"""
        receipt = {
            'id': 1,
            'original_filename': 'receipt.jpg',
            'stored_filename': 'stored.jpg',
            'file_path': None,
            'vendor': 'Store',
            'amount': 10.00,
            'date': datetime(2024, 1, 15),
            'confidence': 2,
            'selected_method': 'tesseract',
            'raw_text': None,
            'metadata': {},
            'created_at': '2024-01-15',
            'updated_at': '2024-01-15'
        }
        mock_get_by_id.return_value = receipt
        mock_delete.return_value = True
        
        response = client.delete('/api/receipts/1')
        
        assert response.status_code == 200
    
    # ========== Not Found Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_not_found(self, mock_get_by_id, client):
        """Test error when receipt does not exist"""
        mock_get_by_id.return_value = None
        
        response = client.delete('/api/receipts/999')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    @patch.object(rm, 'delete')
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_delete_returns_false(self, mock_get_by_id, mock_delete, client, sample_receipts):
        """Test error when delete operation fails"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_delete.return_value = False
        
        response = client.delete('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Failed to delete' in data['error']
    
    # ========== Error Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_database_error_get(self, mock_get_by_id, client):
        """Test handling database errors on get"""
        mock_get_by_id.side_effect = DatabaseError("Connection failed")
        
        response = client.delete('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']
    
    @patch.object(rm, 'delete')
    @patch.object(rm, 'get_by_id')
    def test_delete_receipt_database_error_delete(self, mock_get_by_id, mock_delete, client, sample_receipts):
        """Test handling database errors on delete"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_delete.side_effect = DatabaseError("Delete failed")
        
        response = client.delete('/api/receipts/1')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']
    
    # ========== Edge Cases ==========
    
    def test_delete_receipt_invalid_id(self, client):
        """Test with non-integer ID"""
        response = client.delete('/api/receipts/abc')
        
        assert response.status_code == 404


class TestGetReceiptImageEndpoint:
    """Tests for GET /api/receipts/<receipt_id>/image endpoint"""
    
    # ========== Success Cases ==========
    
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_image_success_jpg(self, mock_get_by_id, mock_exists, client, sample_receipts, tmp_path):
        """Test successfully retrieving a JPG image"""
        # Create a temp image file
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b'\xFF\xD8\xFF\xE0' + b'\x00' * 100)
        
        receipt = {**sample_receipts[0], 'file_path': str(image_path)}
        mock_get_by_id.return_value = receipt
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('flask.send_file') as mock_send:
                mock_send.return_value = MagicMock()
                response = client.get('/api/receipts/1/image')
                # The endpoint should attempt to send the file
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_image_not_found_receipt(self, mock_get_by_id, client):
        """Test error when receipt does not exist"""
        mock_get_by_id.return_value = None
        
        response = client.get('/api/receipts/999/image')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_image_no_file_path(self, mock_get_by_id, client):
        """Test error when receipt has no file path"""
        receipt = {
            'id': 1,
            'original_filename': 'receipt.jpg',
            'stored_filename': 'stored.jpg',
            'file_path': None,
            'vendor': 'Store',
            'amount': 10.00,
            'date': datetime(2024, 1, 15),
            'confidence': 2,
            'selected_method': 'tesseract',
            'raw_text': None,
            'metadata': {},
            'created_at': '2024-01-15',
            'updated_at': '2024-01-15'
        }
        mock_get_by_id.return_value = receipt
        
        response = client.get('/api/receipts/1/image')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'No image file' in data['error']
    
    @patch('pathlib.Path.exists', return_value=False)
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_image_file_not_exists(self, mock_get_by_id, mock_exists, client, sample_receipts):
        """Test error when file does not exist on disk"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.get('/api/receipts/1/image')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    # ========== Database Error Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_get_receipt_image_database_error(self, mock_get_by_id, client):
        """Test handling database errors"""
        mock_get_by_id.side_effect = DatabaseError("Connection failed")
        
        response = client.get('/api/receipts/1/image')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']


class TestReprocessReceiptEndpoint:
    """Tests for POST /api/receipts/<receipt_id>/reprocess endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'update')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_success(
        self, mock_get_by_id, mock_exists, mock_loader, mock_extractor, 
        mock_update, client, sample_receipts, sample_receipt
    ):
        """Test successfully reprocessing a receipt"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_update.return_value = {**sample_receipts[0], 'confidence': 3}
        
        response = client.post('/api/receipts/1/reprocess')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'reprocessed' in data['data']['message'].lower()
        assert 'reprocessing' in data['data']
    
    @patch.object(rm, 'update')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_keep_overrides(
        self, mock_get_by_id, mock_exists, mock_loader, mock_extractor, 
        mock_update, client, sample_receipts, sample_receipt
    ):
        """Test reprocessing with keep_overrides=True"""
        receipt_with_manual = {**sample_receipts[0], 'vendor': 'Manual Vendor'}
        mock_get_by_id.return_value = receipt_with_manual
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_update.return_value = receipt_with_manual
        
        response = client.post(
            '/api/receipts/1/reprocess',
            data=json.dumps({'keep_overrides': True}),
            content_type='application/json'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['reprocessing']['kept_overrides'] is True
    
    # ========== Not Found / Error Cases ==========
    
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_not_found(self, mock_get_by_id, client):
        """Test error when receipt does not exist"""
        mock_get_by_id.return_value = None
        
        response = client.post('/api/receipts/999/reprocess')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_no_file_path(self, mock_get_by_id, client):
        """Test error when receipt has no file path"""
        receipt = {
            'id': 1,
            'original_filename': 'receipt.jpg',
            'stored_filename': 'stored.jpg',
            'file_path': None,
            'vendor': 'Store',
            'amount': 10.00,
            'date': datetime(2024, 1, 15),
            'confidence': 2,
            'selected_method': 'tesseract',
            'raw_text': None,
            'metadata': {},
            'created_at': '2024-01-15',
            'updated_at': '2024-01-15'
        }
        mock_get_by_id.return_value = receipt
        
        response = client.post('/api/receipts/1/reprocess')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'No image file' in data['error']
    
    @patch('pathlib.Path.exists', return_value=False)
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_file_not_exists(self, mock_get_by_id, mock_exists, client, sample_receipts):
        """Test error when file does not exist on disk"""
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.post('/api/receipts/1/reprocess')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert 'not found' in data['error'].lower()
    
    @patch.object(receipt_loader, 'process_files')
    @patch('pathlib.Path.exists', return_value=True)
    @patch.object(rm, 'get_by_id')
    def test_reprocess_receipt_loader_returns_empty(
        self, mock_get_by_id, mock_exists, mock_loader, client, sample_receipts
    ):
        """Test error when loader returns no receipts"""
        mock_get_by_id.return_value = sample_receipts[0]
        mock_loader.return_value = []
        
        response = client.post('/api/receipts/1/reprocess')
        data = json.loads(response.data)
        
        assert response.status_code == 422
        assert 'Unable to reprocess' in data['error']


class TestGetReceiptStatsEndpoint:
    """Tests for GET /api/receipts/stats endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'get_stats')
    def test_get_stats_success(self, mock_get_stats, client):
        """Test successfully retrieving statistics"""
        mock_get_stats.return_value = {
            'total_receipts': 100,
            'total_amount': 5000.00,
            'avg_amount': 50.00,
            'avg_confidence': 2.5,
            'unique_vendors': 25,
            'earliest_date': '2024-01-01',
            'latest_date': '2024-06-30',
            'high_confidence_count': 40,
            'top_vendors': [
                {'vendor': 'Walmart', 'count': 20, 'total': 1000.00},
                {'vendor': 'Target', 'count': 15, 'total': 750.00}
            ]
        }
        
        response = client.get('/api/receipts/stats')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert 'statistics' in data['data']
        
        stats = data['data']['statistics']
        assert stats['total_receipts'] == 100
        assert stats['total_amount'] == 5000.00
        assert stats['average_amount'] == 50.00
        assert stats['unique_vendors'] == 25
        assert stats['high_confidence_count'] == 40
        assert 'date_range' in stats
        assert 'top_vendors' in stats
    
    @patch.object(rm, 'get_stats')
    def test_get_stats_empty_database(self, mock_get_stats, client):
        """Test statistics with empty database"""
        mock_get_stats.return_value = {
            'total_receipts': 0,
            'total_amount': None,
            'avg_amount': None,
            'avg_confidence': None,
            'unique_vendors': 0,
            'earliest_date': None,
            'latest_date': None,
            'high_confidence_count': 0,
            'top_vendors': []
        }
        
        response = client.get('/api/receipts/stats')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['data']['statistics']['total_receipts'] == 0
        assert data['data']['statistics']['total_amount'] is None
        assert data['data']['statistics']['top_vendors'] == []
    
    # ========== Error Cases ==========
    
    @patch.object(rm, 'get_stats')
    def test_get_stats_database_error(self, mock_get_stats, client):
        """Test handling database errors"""
        mock_get_stats.side_effect = DatabaseError("Connection failed")
        
        response = client.get('/api/receipts/stats')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']
    
    @patch.object(rm, 'get_stats')
    def test_get_stats_unexpected_error(self, mock_get_stats, client):
        """Test handling unexpected exceptions"""
        mock_get_stats.side_effect = Exception("Unexpected error")
        
        response = client.get('/api/receipts/stats')
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Internal server error' in data['error']
    
    # ========== HTTP Method Tests ==========
    
    def test_get_stats_wrong_method_post(self, client):
        """Test that POST method is not allowed"""
        response = client.post('/api/receipts/stats')
        
        assert response.status_code == 405


class TestUploadReceiptEndpoint:
    """Tests for POST /api/receipts/upload endpoint"""
    
    # ========== Success Cases ==========
    
    @patch.object(rm, 'get_by_id')
    @patch.object(rm, 'save')
    @patch('shutil.copy2')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_upload_receipt_success(
        self, mock_loader, mock_extractor, mock_copy, mock_save, 
        mock_get_by_id, client, sample_image_file, sample_receipt, sample_receipts
    ):
        """Test successfully uploading a receipt"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_save.return_value = 1
        mock_get_by_id.return_value = sample_receipts[0]
        
        response = client.post(
            '/api/receipts/upload',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 201
        assert 'receipt' in data['data']
        assert 'uploaded' in data['data']['message'].lower()
    
    @patch.object(rm, 'get_by_id')
    @patch.object(rm, 'save')
    @patch('shutil.copy2')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_upload_receipt_with_overrides(
        self, mock_loader, mock_extractor, mock_copy, mock_save, 
        mock_get_by_id, client, sample_image_file, sample_receipt, sample_receipts
    ):
        """Test uploading with manual overrides"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_save.return_value = 1
        mock_get_by_id.return_value = {**sample_receipts[0], 'vendor': 'Override Vendor'}
        
        response = client.post(
            '/api/receipts/upload',
            data={
                'file': (sample_image_file, 'receipt.jpg'),
                'vendor': 'Override Vendor',
                'amount': '100.00',
                'date': '2024-02-20'
            },
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 201
    
    # ========== Validation Error Cases ==========
    
    def test_upload_receipt_no_file(self, client):
        """Test error when no file provided"""
        response = client.post(
            '/api/receipts/upload',
            data={},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'No file provided' in data['error']
    
    def test_upload_receipt_empty_filename(self, client):
        """Test error with empty filename"""
        response = client.post(
            '/api/receipts/upload',
            data={'file': (BytesIO(b''), '')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'No file selected' in data['error']
    
    def test_upload_receipt_invalid_file_type(self, client):
        """Test error with invalid file type"""
        response = client.post(
            '/api/receipts/upload',
            data={'file': (BytesIO(b'content'), 'receipt.doc')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'Invalid file type' in data['error']
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_upload_receipt_invalid_override_amount(
        self, mock_loader, mock_extractor, client, sample_image_file, sample_receipt
    ):
        """Test error with invalid amount override"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/upload',
            data={
                'file': (sample_image_file, 'receipt.jpg'),
                'amount': 'not-a-number'
            },
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'amount' in data['error'].lower()
    
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    def test_upload_receipt_invalid_override_date(
        self, mock_loader, mock_extractor, client, sample_image_file, sample_receipt
    ):
        """Test error with invalid date override"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        
        response = client.post(
            '/api/receipts/upload',
            data={
                'file': (sample_image_file, 'receipt.jpg'),
                'date': 'invalid-date'
            },
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert 'date' in data['error'].lower()
    
    # ========== Processing Error Cases ==========
    
    @patch.object(receipt_loader, 'process_files')
    def test_upload_receipt_loader_returns_empty(
        self, mock_loader, client, sample_image_file
    ):
        """Test error when loader returns no receipts"""
        mock_loader.return_value = []
        
        response = client.post(
            '/api/receipts/upload',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 422
        assert 'Unable to process' in data['error']
    
    @patch('shutil.copy2')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    @patch.object(rm, 'save')
    def test_upload_receipt_save_returns_none(
        self, mock_save, mock_loader, mock_extractor, mock_copy, 
        client, sample_image_file, sample_receipt
    ):
        """Test error when save returns None"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_save.return_value = None
        
        response = client.post(
            '/api/receipts/upload',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Failed to save' in data['error']
    
    @patch('shutil.copy2')
    @patch.object(receipt_extractor, 'process_receipt')
    @patch.object(receipt_loader, 'process_files')
    @patch.object(rm, 'save')
    def test_upload_receipt_database_error(
        self, mock_save, mock_loader, mock_extractor, mock_copy, 
        client, sample_image_file, sample_receipt
    ):
        """Test handling database errors"""
        mock_loader.return_value = [sample_receipt]
        mock_extractor.return_value = sample_receipt
        mock_save.side_effect = DatabaseError("Save failed")
        
        response = client.post(
            '/api/receipts/upload',
            data={'file': (sample_image_file, 'receipt.jpg')},
            content_type='multipart/form-data'
        )
        data = json.loads(response.data)
        
        assert response.status_code == 500
        assert 'Database error' in data['error']

if __name__ == "__main__":
    pytest.main([__file__, "-v"])