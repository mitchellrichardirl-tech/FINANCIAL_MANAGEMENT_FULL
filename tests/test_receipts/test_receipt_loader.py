import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.receipts.receipt_loader import ReceiptLoader
from src.models.receipt import Receipt
from src.models.processing_config import ProcessingConfig


class TestReceiptLoader:
    """Test the ReceiptLoader class."""
    
    @pytest.fixture
    def mock_processing_config(self):
        """Create a mock ProcessingConfig."""
        return Mock(spec=ProcessingConfig)
    
    @pytest.fixture
    def sample_images(self):
        """Create sample images for testing."""
        return [
            np.ones((100, 100, 3), dtype=np.uint8) * 128,
            np.ones((150, 150, 3), dtype=np.uint8) * 200,
            np.ones((200, 200, 3), dtype=np.uint8) * 255,
        ]
    
    @pytest.fixture
    def sample_processed_images(self):
        """Create sample processed images."""
        return [
            np.zeros((100, 100), dtype=np.uint8),
            np.zeros((150, 150), dtype=np.uint8),
            np.zeros((200, 200), dtype=np.uint8),
        ]
    
    def test_init_default_config(self):
        """Test initialization with default config."""
        loader = ReceiptLoader()
        
        assert loader.processing_config is not None
        assert isinstance(loader.processing_config, ProcessingConfig)
        assert loader.image_loader is not None
    
    def test_init_custom_config(self, mock_processing_config):
        """Test initialization with custom config."""
        loader = ReceiptLoader(processing_config=mock_processing_config)
        
        assert loader.processing_config == mock_processing_config
        assert loader.image_loader is not None
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_single_page_as_list(self, mock_image_loader_class, 
                                              mock_image_processor_class, sample_images):
        """Test processing a single-page file returning a list."""
        # Setup ImageLoader mock
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [sample_images[0]]
        mock_image_loader_class.return_value = mock_loader_instance
        
        # Setup ImageProcessor mock
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_file("test.jpg", yield_pages=False)
        
        # Assertions
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], Receipt)
        assert results[0].original_filename == Path("test.jpg")
        assert results[0].page_number == 0
        assert np.array_equal(results[0].original_image, sample_images[0])
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_multiple_pages_as_list(self, mock_image_loader_class,
                                                 mock_image_processor_class,
                                                 sample_images, sample_processed_images):
        """Test processing a multi-page PDF returning a list."""
        # Setup ImageLoader mock
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = sample_images
        mock_image_loader_class.return_value = mock_loader_instance
        
        # Setup ImageProcessor mock
        mock_processor_instance = Mock()
        mock_processor_instance.process.side_effect = sample_processed_images
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_file("test.pdf", yield_pages=False)
        
        # Assertions
        assert isinstance(results, list)
        assert len(results) == 3
        
        for i, receipt in enumerate(results):
            assert isinstance(receipt, Receipt)
            assert receipt.original_filename == Path("test.pdf")
            assert receipt.page_number == i
            assert np.array_equal(receipt.original_image, sample_images[i])
            assert np.array_equal(receipt.processed_images, sample_processed_images[i])
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_yield_pages(self, mock_image_loader_class,
                                     mock_image_processor_class, sample_images):
        """Test processing file with yield_pages=True returns iterator."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = sample_images
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_file("test.pdf", yield_pages=True)
        
        # Assertions - check it's a generator
        from collections.abc import Iterator
        assert isinstance(results, Iterator)
        
        # Consume the iterator
        receipts = list(results)
        assert len(receipts) == 3
        
        for receipt in receipts:
            assert isinstance(receipt, Receipt)
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_with_path_object(self, mock_image_loader_class,
                                           mock_image_processor_class, sample_images):
        """Test processing file with Path object instead of string."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [sample_images[0]]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        file_path = Path("test.jpg")
        results = loader.process_file(file_path, yield_pages=False)
        
        # Assertions
        assert len(results) == 1
        assert results[0].original_filename == file_path
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_processing_error(self, mock_image_loader_class,
                                          mock_image_processor_class, sample_images):
        """Test handling of processing errors for individual images."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = sample_images
        mock_image_loader_class.return_value = mock_loader_instance
        
        # First image processes fine, second fails, third processes fine
        mock_processor_instance = Mock()
        mock_processor_instance.process.side_effect = [
            np.zeros((100, 100), dtype=np.uint8),
            Exception("Processing failed"),
            np.zeros((200, 200), dtype=np.uint8),
        ]
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_file("test.pdf", yield_pages=False)
        
        # Should have 2 results (skipped the failed one)
        assert len(results) == 2
        assert results[0].page_number == 0
        assert results[1].page_number == 2
    
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_file_loading_error(self, mock_image_loader_class):
        """Test handling of file loading errors."""
        # Setup mock to raise exception
        mock_loader_instance = Mock()
        mock_loader_instance.load.side_effect = FileNotFoundError("File not found")
        mock_image_loader_class.return_value = mock_loader_instance
        
        # Create loader
        loader = ReceiptLoader()
        
        # Should raise the exception
        with pytest.raises(FileNotFoundError):
            loader.process_file("nonexistent.pdf", yield_pages=False)
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_single_file_as_string(self, mock_image_loader_class,
                                                 mock_image_processor_class, sample_images):
        """Test process_files with single file path as string."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [sample_images[0]]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_files("test.jpg", yield_pages=True)
        
        # Assertions
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].original_filename == Path("test.jpg")
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_single_file_as_path(self, mock_image_loader_class,
                                               mock_image_processor_class, sample_images):
        """Test process_files with single file path as Path object."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [sample_images[0]]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process file
        loader = ReceiptLoader()
        results = loader.process_files(Path("test.jpg"), yield_pages=True)
        
        # Assertions
        assert isinstance(results, list)
        assert len(results) == 1
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_multiple_files(self, mock_image_loader_class,
                                         mock_image_processor_class):
        """Test processing multiple files."""
        # Setup mocks - each file has different number of pages
        mock_loader_instance = Mock()
        mock_loader_instance.load.side_effect = [
            [np.ones((100, 100, 3), dtype=np.uint8)],  # 1 page
            [np.ones((100, 100, 3), dtype=np.uint8), np.ones((100, 100, 3), dtype=np.uint8)],  # 2 pages
            [np.ones((100, 100, 3), dtype=np.uint8)],  # 1 page
        ]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process files
        loader = ReceiptLoader()
        file_paths = ["file1.jpg", "file2.pdf", "file3.png"]
        results = loader.process_files(file_paths, yield_pages=True)
        
        # Assertions
        assert isinstance(results, list)
        assert len(results) == 4  # Total pages across all files
        
        # Check source files
        assert results[0].original_filename == Path("file1.jpg")
        assert results[1].original_filename == Path("file2.pdf")
        assert results[2].original_filename == Path("file2.pdf")
        assert results[3].original_filename == Path("file3.png")
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_with_yield(self, mock_image_loader_class,
                                     mock_image_processor_class):
        """Test process_files with yield_pages=True."""
        # Setup mocks
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = [np.ones((100, 100, 3), dtype=np.uint8)]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process files
        loader = ReceiptLoader()
        results = loader.process_files(["file1.jpg", "file2.jpg"], yield_pages=False)
        
        # Assertions
        from collections.abc import Iterator
        assert isinstance(results, Iterator)
        receipts = list(results)
        assert len(receipts) == 2
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_with_failures(self, mock_image_loader_class,
                                        mock_image_processor_class):
        """Test process_files handles individual file failures gracefully."""
        # Setup mocks - second file fails to load
        mock_loader_instance = Mock()
        mock_loader_instance.load.side_effect = [
            [np.ones((100, 100, 3), dtype=np.uint8)],  # Success
            FileNotFoundError("File not found"),         # Failure
            [np.ones((100, 100, 3), dtype=np.uint8)],  # Success
        ]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader and process files
        loader = ReceiptLoader()
        file_paths = ["file1.jpg", "missing.pdf", "file3.jpg"]
        results = loader.process_files(file_paths, yield_pages=True)
        
        # Should have results from successful files only
        assert len(results) == 2
        assert results[0].original_filename == Path("file1.jpg")
        assert results[1].original_filename == Path("file3.jpg")
    
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_process_files_empty_list(self, mock_image_loader_class):
        """Test process_files with empty file list."""
        loader = ReceiptLoader()
        results = loader.process_files([], yield_pages=True)
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    @patch('src.receipts.receipt_loader.ImageProcessor')
    @patch('src.receipts.receipt_loader.ImageLoader')
    def test_custom_processing_config_passed_to_processor(self, mock_image_loader_class,
                                                        mock_image_processor_class,
                                                        mock_processing_config):
        """Test that custom processing config is passed to ImageProcessor."""
        # Setup mocks
        mock_loader_instance = Mock()
        test_image = np.ones((100, 100, 3), dtype=np.uint8)
        mock_loader_instance.load.return_value = [test_image]
        mock_image_loader_class.return_value = mock_loader_instance
        
        mock_processor_instance = Mock()
        mock_processor_instance.process.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_image_processor_class.return_value = mock_processor_instance
        
        # Create loader with custom config and process file
        loader = ReceiptLoader(processing_config=mock_processing_config)
        results = loader.process_file("test.jpg", yield_pages=False)
        
        # Verify ImageProcessor was called once
        mock_image_processor_class.assert_called_once()
        
        # Get the actual call arguments
        call_args, call_kwargs = mock_image_processor_class.call_args
        
        # Verify the config was passed correctly
        assert call_kwargs['config'] == mock_processing_config
        
        # Verify the image was passed correctly (numpy array comparison)
        assert len(call_args) == 1
        assert np.array_equal(call_args[0], test_image)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])