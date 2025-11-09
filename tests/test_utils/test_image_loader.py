import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import cv2
from PIL import Image

from src.utils.image_loader import ImageLoader, ImageFormat


class TestImageFormat:
    """Test the ImageFormat enum."""
    
    def test_image_formats(self):
        """Test that all image formats are properly defined."""
        assert '.jpg' in ImageFormat.JPEG.value
        assert '.jpeg' in ImageFormat.JPEG.value
        assert '.png' in ImageFormat.PNG.value
        assert '.pdf' in ImageFormat.PDF.value
        assert '.tiff' in ImageFormat.TIFF.value
        assert '.tif' in ImageFormat.TIFF.value
        assert '.bmp' in ImageFormat.BMP.value


class TestImageLoader:
    """Test the ImageLoader class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def create_test_image(self, temp_dir):
        """Create a test image file."""
        def _create(filename: str, size: tuple = (100, 100), color: tuple = (255, 0, 0)):
            # Create image with PIL
            img = Image.new('RGB', size, color)
            filepath = temp_dir / filename
            img.save(filepath)
            return filepath
        return _create
    
    def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            ImageLoader.load("nonexistent_file.jpg")
        assert "File not found" in str(exc_info.value)
    
    def test_load_unsupported_format(self, temp_dir):
        """Test loading a file with unsupported format."""
        # Create a dummy file with unsupported extension
        unsupported_file = temp_dir / "test.xyz"
        unsupported_file.write_text("dummy content")
        
        with pytest.raises(ValueError) as exc_info:
            ImageLoader.load(unsupported_file)
        assert "Unsupported file format: .xyz" in str(exc_info.value)
    
    def test_load_jpeg_with_opencv(self, create_test_image):
        """Test loading a JPEG image using OpenCV path."""
        # Create test JPEG
        jpeg_path = create_test_image("test.jpg", size=(200, 150))
        
        # Load the image
        images = ImageLoader.load(jpeg_path)
        
        # Verify
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        assert images[0].shape == (150, 200, 3)  # Height, Width, Channels
    
    def test_load_png_with_opencv(self, create_test_image):
        """Test loading a PNG image."""
        png_path = create_test_image("test.png", size=(100, 100))
        
        images = ImageLoader.load(png_path)
        
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        assert images[0].shape == (100, 100, 3)
    
    @patch('cv2.imread')
    def test_load_image_opencv_fallback_to_pil(self, mock_imread, create_test_image):
        """Test fallback to PIL when OpenCV fails."""
        # Make OpenCV fail
        mock_imread.return_value = None
        
        # Create test image
        image_path = create_test_image("test.jpg")
        
        # Load should succeed with PIL
        images = ImageLoader.load(image_path)
        
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        mock_imread.assert_called_once()
    
    @patch('cv2.imread')
    @patch('PIL.Image.open')
    def test_load_image_both_methods_fail(self, mock_pil_open, mock_imread, temp_dir):
        """Test when both OpenCV and PIL fail to load image."""
        # Make both methods fail
        mock_imread.return_value = None
        mock_pil_open.side_effect = Exception("PIL failed")
        
        # Create dummy file
        image_path = temp_dir / "test.jpg"
        image_path.write_text("dummy")
        
        with pytest.raises(Exception) as exc_info:
            ImageLoader.load(image_path)
        assert "PIL failed" in str(exc_info.value)
    
    @patch('pdf2image.convert_from_path')
    def test_load_pdf_single_page(self, mock_convert):
        """Test loading a single-page PDF."""
        # Create mock PIL image
        print("debugging")
        mock_pil_image = MagicMock()
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_pil_image.__array__ = lambda *args, **kwargs: mock_array
        mock_convert.return_value = [mock_pil_image]
        
        # Create dummy PDF path
        pdf_path = Path("test.pdf")
        
        with patch('pathlib.Path.exists', return_value=True):
            images = ImageLoader.load(pdf_path)
        
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        assert images[0].shape == (100, 100, 3)
        mock_convert.assert_called_once_with(pdf_path)
    
    @patch('pdf2image.convert_from_path')
    def test_load_pdf_multiple_pages(self, mock_convert):
        """Test loading a multi-page PDF."""
        # Create mock PIL images for 3 pages
        mock_images = []
        for i in range(3):
            mock_pil_image = MagicMock()
            mock_array = np.zeros((100 + i*10, 100, 3), dtype=np.uint8)
            mock_pil_image.__array__ = lambda *args, arr=mock_array, **kwargs: arr
            mock_images.append(mock_pil_image)
        
        mock_convert.return_value = mock_images
        
        pdf_path = Path("test.pdf")
        
        with patch('pathlib.Path.exists', return_value=True):
            images = ImageLoader.load(pdf_path)
        
        assert len(images) == 3
        assert images[0].shape == (100, 100, 3)
        assert images[1].shape == (110, 100, 3)
        assert images[2].shape == (120, 100, 3)
    
    @patch('pdf2image.convert_from_path')
    def test_load_pdf_failure(self, mock_convert):
        """Test PDF loading failure."""
        mock_convert.side_effect = Exception("PDF conversion failed")
        
        pdf_path = Path("test.pdf")
        
        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(Exception) as exc_info:
                ImageLoader.load(pdf_path)
            assert "PDF conversion failed" in str(exc_info.value)
    
    def test_load_with_string_path(self, create_test_image):
        """Test loading with string path instead of Path object."""
        image_path = create_test_image("test.jpg")
        
        # Use string path
        images = ImageLoader.load(str(image_path))
        
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
    
    def test_bgr_to_rgb_conversion_all_channels(self, temp_dir):
        """Test that BGR images are converted to RGB correctly for all channels."""
        # Create an image with different values in each channel
        bgr_image = np.zeros((10, 10, 3), dtype=np.uint8)
        bgr_image[:, :] = [100, 150, 200]  # B=100, G=150, R=200 in BGR
        
        image_path = temp_dir / "test_bgr.png"
        cv2.imwrite(str(image_path), bgr_image)
        
        # Load the image
        images = ImageLoader.load(image_path)
        
        # After conversion BGR->RGB: [100, 150, 200] should become [200, 150, 100]
        assert np.all(images[0][0, 0] == [200, 150, 100])  # R=200, G=150, B=100 in RGB

    def test_bgr_to_rgb_conversion_jpeg(self, temp_dir):
        """Test that BGR images are converted to RGB."""
        # Create a specific color pattern to test BGR->RGB conversion
        bgr_image = np.zeros((10, 10, 3), dtype=np.uint8)
        bgr_image[:, :] = [255, 0, 0]  # Blue in BGR
        
        image_path = temp_dir / "test_bgr.jpg"
        cv2.imwrite(str(image_path), bgr_image)
        
        # Load the image
        images = ImageLoader.load(image_path)
        
        # After conversion, should be red in RGB (with tolerance for JPEG)
        expected = np.array([0, 0, 255])
        actual = images[0][0, 0]
        assert np.allclose(actual, expected, atol=5)  # Allow 5 units of difference
    
    @pytest.mark.parametrize("extension", ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'])
    def test_supported_formats(self, create_test_image, extension):
        """Test loading various supported image formats."""
        if extension in ['.tiff', '.tif']:
            # Create TIFF with PIL
            img = Image.new('RGB', (50, 50), color='red')
            image_path = create_test_image(f"test{extension}")
            img.save(image_path, format='TIFF')
        else:
            image_path = create_test_image(f"test{extension}")
        
        images = ImageLoader.load(image_path)
        
        assert len(images) == 1
        assert isinstance(images[0], np.ndarray)
        assert len(images[0].shape) == 3  # Should have 3 dimensions
    
    def test_load_grayscale_image(self, temp_dir):
        """Test loading a grayscale image."""
        # Create grayscale image
        gray_img = Image.new('L', (100, 100), color=128)
        gray_path = temp_dir / "gray.jpg"
        gray_img.save(gray_path)
        
        images = ImageLoader.load(gray_path)
        
        assert len(images) == 1
        # OpenCV will load it as BGR, so it will have 3 channels
        # But PIL fallback might load as 2D
        assert isinstance(images[0], np.ndarray)


class TestImageLoaderIntegration:
    """Integration tests that require actual files."""
    
    @pytest.mark.integration
    def test_load_real_jpeg(self, tmp_path):
        """Test loading an actual JPEG file."""
        # Create a real JPEG file
        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(img_array, mode='RGB')
        jpeg_path = tmp_path / "real_test.jpg"
        img.save(jpeg_path, 'JPEG')
        
        # Load and verify
        images = ImageLoader.load(jpeg_path)
        assert len(images) == 1
        assert images[0].shape == (100, 100, 3)
    
    @pytest.mark.integration
    @pytest.mark.skipif(not Path("/usr/bin/pdftoppm").exists(), 
                       reason="pdf2image dependencies not installed")
    def test_load_real_pdf(self, tmp_path):
        """Test loading a real PDF file (requires poppler-utils)."""
        # This test will be skipped if pdf2image dependencies aren't installed
        # You would need to create a simple PDF for this test
        pass


# Fixtures for pytest configuration
@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration between tests."""
    import logging
    # Get the logger used in image_loader
    logger = logging.getLogger('image_loader')
    logger.handlers.clear()
    yield
    logger.handlers.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])