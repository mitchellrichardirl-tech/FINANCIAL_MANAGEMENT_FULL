import pytest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
from PIL import Image

from src.utils.image_processor import ImageProcessor, ProcessingConfig


class TestProcessingConfig:
    """Test the ProcessingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ProcessingConfig()
        assert config.max_dimension == 1500
        assert config.denoise_filter_size == 3
        assert config.contrast_factor == 2.0
        assert config.sharpness_factor == 1.5
        assert config.clahe_clip_limit == 2.0
        assert config.clahe_tile_size == (8, 8)
        assert config.bilateral_d == 9
        assert config.bilateral_sigma_color == 75
        assert config.bilateral_sigma_space == 75
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ProcessingConfig(
            max_dimension=2000,
            denoise_filter_size=5,
            contrast_factor=1.5
        )
        assert config.max_dimension == 2000
        assert config.denoise_filter_size == 5
        assert config.contrast_factor == 1.5
        # Defaults should remain
        assert config.sharpness_factor == 1.5


class TestImageProcessor:
    """Test the ImageProcessor class."""
    
    # @pytest.fixture
    # def sample_gray_image(self):
    #     """Create a sample grayscale image."""
    #     return np.ones((100, 100), dtype=np.uint8) * 128
    
    # @pytest.fixture
    # def sample_color_image(self):
    #     """Create a sample color image (BGR)."""
    #     return np.ones((100, 100, 3), dtype=np.uint8) * 128
    
    # @pytest.fixture
    # def sample_rgba_image(self):
    #     """Create a sample RGBA image."""
    #     return np.ones((100, 100, 4), dtype=np.uint8) * 128
    
    # @pytest.fixture
    # def large_image(self):
    #     """Create a large image that exceeds max dimension."""
    #     return np.ones((2000, 2000, 3), dtype=np.uint8) * 128
    
    def test_init_with_grayscale_image(self, sample_gray_image):
        """Test initialization with a grayscale image."""
        processor = ImageProcessor(sample_gray_image)
        assert processor.gray_image.shape == (100, 100)
        assert np.array_equal(processor.original_image, sample_gray_image)
    
    def test_init_with_color_image(self, sample_color_image):
        """Test initialization with a color image."""
        processor = ImageProcessor(sample_color_image)
        assert len(processor.gray_image.shape) == 2  # Should be grayscale
        assert processor.gray_image.shape == (100, 100)
    
    def test_init_with_rgba_image(self, sample_rgba_image):
        """Test initialization with an RGBA image."""
        processor = ImageProcessor(sample_rgba_image)
        assert len(processor.gray_image.shape) == 2  # Should be grayscale
        assert processor.gray_image.shape == (100, 100)
    
    def test_init_with_custom_config(self, sample_gray_image):
        """Test initialization with custom config."""
        config = ProcessingConfig(max_dimension=500)
        processor = ImageProcessor(sample_gray_image, config)
        assert processor.config.max_dimension == 500
    
    def test_available_methods(self, sample_gray_image):
        """Test that all expected methods are available."""
        processor = ImageProcessor(sample_gray_image)
        expected_methods = [
            "denoise",
            "correct_skew",
            "apply_clahe",
            "apply_bilateral_threshold",
            "apply_morphological"
        ]
        for method in expected_methods:
            assert method in processor.available_methods
            assert callable(processor.available_methods[method])
    
    def test_resize_if_needed_small_image(self):
        """Test that small images are not resized."""
        image = np.ones((100, 100, 3), dtype=np.uint8)
        config = ProcessingConfig(max_dimension=1500)
        resized = ImageProcessor._resize_if_needed(image, config)
        assert resized.shape == (100, 100, 3)
    
    def test_resize_if_needed_large_image(self):
        """Test that large images are resized."""
        image = np.ones((2000, 3000, 3), dtype=np.uint8)
        config = ProcessingConfig(max_dimension=1500)
        resized = ImageProcessor._resize_if_needed(image, config)
        
        # Max dimension should be 1500
        assert max(resized.shape[:2]) == 1500
        # Aspect ratio should be preserved
        assert resized.shape[0] / resized.shape[1] == pytest.approx(2000 / 3000)
    
    def test_resize_if_needed_exact_max(self):
        """Test image exactly at max dimension."""
        image = np.ones((1500, 1500, 3), dtype=np.uint8)
        config = ProcessingConfig(max_dimension=1500)
        resized = ImageProcessor._resize_if_needed(image, config)
        assert resized.shape == (1500, 1500, 3)
    
    def test_convert_to_grayscale_color_image(self):
        """Test conversion of color image to grayscale."""
        color_image = np.zeros((100, 100, 3), dtype=np.uint8)
        color_image[:, :] = [100, 150, 200]  # BGR
        
        gray = ImageProcessor._convert_to_grayscale(color_image)
        
        assert len(gray.shape) == 2
        assert gray.shape == (100, 100)
        assert gray.dtype == np.uint8
    
    def test_convert_to_grayscale_rgba_image(self):
        """Test conversion of RGBA image to grayscale."""
        rgba_image = np.zeros((100, 100, 4), dtype=np.uint8)
        rgba_image[:, :] = [100, 150, 200, 255]  # BGRA
        
        gray = ImageProcessor._convert_to_grayscale(rgba_image)
        
        assert len(gray.shape) == 2
        assert gray.shape == (100, 100)
    
    def test_convert_to_grayscale_already_gray(self):
        """Test that grayscale images are returned unchanged."""
        gray_image = np.ones((100, 100), dtype=np.uint8) * 128
        
        result = ImageProcessor._convert_to_grayscale(gray_image)
        
        assert np.array_equal(result, gray_image)
    
    def test_process_single_method_string(self, sample_gray_image):
        """Test processing with a single method as string."""
        processor = ImageProcessor(sample_gray_image)
        result = processor.process("apply_clahe")
        
        assert isinstance(result, np.ndarray)
        assert result.shape == sample_gray_image.shape
    
    def test_process_single_method_list(self, sample_gray_image):
        """Test processing with a single method in a list."""
        processor = ImageProcessor(sample_gray_image)
        result = processor.process(["apply_clahe"])
        
        assert isinstance(result, np.ndarray)
    
    def test_process_multiple_methods(self, sample_gray_image):
        """Test processing with multiple methods."""
        processor = ImageProcessor(sample_gray_image)
        methods = ["apply_clahe", "denoise"]
        result = processor.process(methods)
        
        assert isinstance(result, np.ndarray)
    
    def test_process_all_methods_default(self, sample_gray_image):
        """Test processing with all default methods (None)."""
        processor = ImageProcessor(sample_gray_image)
        result = processor.process(None)
        
        assert isinstance(result, np.ndarray)
    
    def test_process_unknown_method(self, sample_gray_image):
        """Test that unknown methods are skipped without error."""
        processor = ImageProcessor(sample_gray_image)
        original_image = processor.gray_image.copy()
        
        # Process with unknown method
        result = processor.process(["unknown_method"])
        
        # Should return unchanged image (no valid methods applied)
        assert isinstance(result, np.ndarray)
        assert np.array_equal(result, original_image)
    
    def test_process_method_exception(self, sample_gray_image):
        """Test error handling when a method raises an exception."""
        processor = ImageProcessor(sample_gray_image)
        original_image = processor.gray_image.copy()
        
        # Mock a method to raise an exception
        def failing_method():
            raise Exception("Test error")
        
        processor.available_methods["test_method"] = failing_method
        
        # Should not crash
        result = processor.process(["test_method"])
        
        assert isinstance(result, np.ndarray)
        # Image should remain unchanged after failed method
        assert np.array_equal(result, original_image)
    
    def test_denoise(self, noisy_gray_image):
        """Test denoising method applies all processing steps."""
        processor = ImageProcessor(noisy_gray_image)
        original = processor.gray_image.copy()
        
        result = processor._denoise()
        
        # Basic checks
        assert isinstance(result, np.ndarray)
        assert result.shape == noisy_gray_image.shape
        assert result.dtype == np.uint8
        
        # Image should be modified
        assert not np.array_equal(result, original)
        
        # Values should be in valid range
        assert 0 <= result.min() <= 255
        assert 0 <= result.max() <= 255

    def test_denoise_increases_contrast(self):
        """Test that denoise increases contrast (due to contrast enhancement)."""
        # Low contrast image
        image = np.ones((100, 100), dtype=np.uint8) * 128
        image[25:75, 25:75] = 135  # Subtle difference
        
        processor = ImageProcessor(image)
        original_contrast = processor.gray_image.max() - processor.gray_image.min()
        
        result = processor._denoise()
        result_contrast = result.max() - result.min()
        
        # Contrast should increase due to contrast_factor=2.0
        assert result_contrast > original_contrast

    def test_denoise_with_custom_config(self, noisy_gray_image):
        """Test denoising with custom configuration."""
        config = ProcessingConfig(
            denoise_filter_size=5,
            contrast_factor=1.5,
            sharpness_factor=1.2
        )
        processor = ImageProcessor(noisy_gray_image, config)
        
        result = processor._denoise()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == noisy_gray_image.shape

    def test_denoise_uniform_image(self, uniform_gray_image):
        """Test denoising on uniform image (edge case)."""
        processor = ImageProcessor(uniform_gray_image)
        original = processor.gray_image.copy()
        
        result = processor._denoise()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == uniform_gray_image.shape
        # May or may not change, but shouldn't crash
    
    def test_correct_skew(self, sample_gray_image):
        """Test skew correction."""
        # Create an image with some content
        image = np.zeros((100, 100), dtype=np.uint8)
        image[40:60, 40:60] = 255
        
        processor = ImageProcessor(image)
        result = processor._correct_skew()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == image.shape
    
    def test_correct_skew_empty_image(self):
        """Test skew correction on an empty image."""
        empty_image = np.zeros((100, 100), dtype=np.uint8)
        processor = ImageProcessor(empty_image)
        
        # Should handle empty image gracefully (not enough points)
        result = processor._correct_skew()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == empty_image.shape
        # Empty image should remain unchanged
        assert np.array_equal(result, empty_image)

    def test_correct_skew_insufficient_points(self):
        """Test skew correction with too few points."""
        image = np.zeros((100, 100), dtype=np.uint8)
        image[50, 50] = 255  # Single pixel
        image[51, 51] = 255  # Two pixels
        
        processor = ImageProcessor(image)
        original = processor.gray_image.copy()
        
        result = processor._correct_skew()
        
        assert isinstance(result, np.ndarray)
        # Should return unchanged due to insufficient points
        assert np.array_equal(result, original)

    def test_correct_skew_with_content(self):
        """Test skew correction with sufficient content."""
        # Create an image with a rotated rectangle
        image = np.zeros((100, 100), dtype=np.uint8)
        image[40:60, 30:70] = 255  # White rectangle
        
        processor = ImageProcessor(image)
        
        result = processor._correct_skew()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == image.shape
    
    def test_apply_clahe(self, sample_gray_image):
        """Test CLAHE application."""
        processor = ImageProcessor(sample_gray_image)
        original_image = processor.gray_image.copy()
        
        result = processor._apply_clahe()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == original_image.shape
        assert result.dtype == np.uint8
    
    def test_apply_clahe_with_custom_config(self, sample_gray_image):
        """Test CLAHE with custom configuration."""
        config = ProcessingConfig(
            clahe_clip_limit=3.0,
            clahe_tile_size=(16, 16)
        )
        processor = ImageProcessor(sample_gray_image, config)
        
        result = processor._apply_clahe()
        
        assert isinstance(result, np.ndarray)
    
    def test_apply_bilateral_threshold(self, sample_gray_image):
        """Test bilateral filter with threshold."""
        processor = ImageProcessor(sample_gray_image)
        
        result = processor._apply_bilateral_threshold()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == sample_gray_image.shape
        # Result should be binary (only 0 and 255)
        assert set(np.unique(result)).issubset({0, 255})
    
    def test_apply_bilateral_threshold_with_custom_config(self, sample_gray_image):
        """Test bilateral threshold with custom configuration."""
        config = ProcessingConfig(
            bilateral_d=11,
            bilateral_sigma_color=100,
            bilateral_sigma_space=100
        )
        processor = ImageProcessor(sample_gray_image, config)
        
        result = processor._apply_bilateral_threshold()
        
        assert isinstance(result, np.ndarray)
    
    def test_apply_morphological(self, sample_gray_image):
        """Test morphological operations."""
        processor = ImageProcessor(sample_gray_image)
        
        result = processor._apply_morphological()
        
        assert isinstance(result, np.ndarray)
        assert result.shape == sample_gray_image.shape
        # Result should be binary (only 0 and 255)
        assert set(np.unique(result)).issubset({0, 255})
    
    def test_chained_processing(self, sample_gray_image):
        """Test that processing methods can be chained."""
        processor = ImageProcessor(sample_gray_image)
        
        # Apply multiple methods in sequence
        result = processor.process(["apply_clahe", "denoise", "apply_bilateral_threshold"])
        
        assert isinstance(result, np.ndarray)
        assert result.shape == sample_gray_image.shape
    
    def test_gray_image_updated_after_processing(self, sample_gray_image):
        """Test that gray_image is updated after each processing step."""
        processor = ImageProcessor(sample_gray_image)
        original = processor.gray_image.copy()
        
        processor.process(["apply_clahe"])
        after_clahe = processor.gray_image.copy()
        
        processor.process(["denoise"])
        after_denoise = processor.gray_image.copy()
        
        # Images should be different after each step
        assert not np.array_equal(original, after_clahe)
        assert not np.array_equal(after_clahe, after_denoise)
    
    def test_large_image_resized_on_init(self, large_image):
        """Test that large images are resized during initialization."""
        config = ProcessingConfig(max_dimension=1000)
        processor = ImageProcessor(large_image, config)
        
        # Original should be preserved
        assert processor.original_image.shape == (2000, 2000, 3)
        # Gray image should be resized
        assert max(processor.gray_image.shape) <= 1000


class TestImageProcessorEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_process_with_empty_method_list(self):
        """Test processing with an empty method list."""
        image = np.ones((100, 100), dtype=np.uint8) * 128
        processor = ImageProcessor(image)
        
        result = processor.process([])
        
        # Should return unchanged image
        assert np.array_equal(result, processor.gray_image)
    
    def test_process_with_mixed_valid_invalid_methods(self, sample_gray_image):
        """Test processing with mix of valid and invalid methods."""
        processor = ImageProcessor(sample_gray_image)
        original_image = processor.gray_image.copy()
        
        # Mix of valid and invalid - valid ones should still process
        result = processor.process(["apply_clahe", "invalid_method", "denoise"])
        
        assert isinstance(result, np.ndarray)
        # Valid methods were applied, so result should differ from original
        assert not np.array_equal(result, original_image)

    def test_process_skips_invalid_applies_valid(self, sample_gray_image):
        """Test that invalid methods are skipped but valid ones are applied."""
        processor = ImageProcessor(sample_gray_image)
        
        # Track which methods were called
        called_methods = []
        
        def track_calls(method_name):
            original_method = processor.available_methods[method_name]
            def wrapper():
                called_methods.append(method_name)
                return original_method()
            return wrapper
        
        processor.available_methods["apply_clahe"] = track_calls("apply_clahe")
        
        # Process with mix of valid and invalid
        processor.process(["invalid", "apply_clahe", "also_invalid"])
        
        # Only valid method should have been called
        assert "apply_clahe" in called_methods
        assert len(called_methods) == 1

    def test_very_small_image(self):
        """Test processing a very small image."""
        small_image = np.ones((10, 10), dtype=np.uint8) * 128
        processor = ImageProcessor(small_image)
        
        result = processor.process(["apply_clahe"])
        
        assert isinstance(result, np.ndarray)
        assert result.shape == (10, 10)
    
    def test_single_pixel_image(self):
        """Test processing a 1x1 image."""
        tiny_image = np.array([[128]], dtype=np.uint8)
        processor = ImageProcessor(tiny_image)
        
        # Some methods might fail on 1x1 images
        # Just ensure initialization works
        assert processor.gray_image.shape == (1, 1)
    
    def test_binary_image(self):
        """Test processing a binary image."""
        binary_image = np.zeros((100, 100), dtype=np.uint8)
        binary_image[25:75, 25:75] = 255
        
        processor = ImageProcessor(binary_image)
        result = processor.process(["apply_clahe"])
        
        assert isinstance(result, np.ndarray)


class TestImageProcessorIntegration:
    """Integration tests for realistic scenarios."""
    
    # @pytest.fixture
    # def document_like_image(self):
    #     """Create an image that looks like a document."""
    #     img = np.ones((800, 600), dtype=np.uint8) * 255  # White background
    #     # Add some "text" (dark rectangles)
    #     img[100:120, 50:500] = 50
    #     img[150:170, 50:400] = 50
    #     img[200:220, 50:450] = 50
    #     return img
    
    def test_full_document_processing_pipeline(self, document_like_image):
        """Test a complete document processing pipeline."""
        processor = ImageProcessor(document_like_image)
        
        result = processor.process([
            "apply_clahe",
            "denoise",
            "correct_skew",
            "apply_bilateral_threshold"
        ])
        
        assert isinstance(result, np.ndarray)
        assert result.shape == document_like_image.shape
        # Should be binary after threshold
        assert set(np.unique(result)).issubset({0, 255})
    
    @pytest.mark.integration
    def test_realistic_noisy_image(self):
        """Test processing a noisy image."""
        # Create image with noise
        clean = np.ones((200, 200), dtype=np.uint8) * 128
        noise = np.random.normal(0, 25, (200, 200))
        noisy = np.clip(clean + noise, 0, 255).astype(np.uint8)
        
        processor = ImageProcessor(noisy)
        result = processor.process(["denoise", "apply_clahe"])
        
        assert isinstance(result, np.ndarray)
        assert result.shape == noisy.shape
        
        # After contrast enhancement, the image should have:
        # 1. Wider value range (higher contrast)
        value_range_before = noisy.max() - noisy.min()
        value_range_after = result.max() - result.min()
        assert value_range_after >= value_range_before
        
        # 2. Values should still be in valid range
        assert 0 <= result.min() <= 255
        assert 0 <= result.max() <= 255
        
        # 3. Image should be significantly changed
        assert not np.array_equal(result, noisy)

    @pytest.mark.integration
    def test_noise_reduction_only(self):
        """Test that median filter component actually reduces salt-and-pepper noise."""
        # Create image with salt-and-pepper noise
        image = np.ones((200, 200), dtype=np.uint8) * 128
        # Add salt and pepper
        salt_pepper_mask = np.random.random((200, 200)) 
        image[salt_pepper_mask < 0.05] = 0  # 5% pepper
        image[salt_pepper_mask > 0.95] = 255  # 5% salt
        
        # Just test the median filter effect
        from PIL import Image, ImageFilter
        pil_image = Image.fromarray(image)
        filtered = pil_image.filter(ImageFilter.MedianFilter(size=3))
        filtered_array = np.array(filtered)
        
        # Count extreme values
        original_extremes = np.sum((image == 0) | (image == 255))
        filtered_extremes = np.sum((filtered_array == 0) | (filtered_array == 255))
        
        # Median filter should reduce salt-and-pepper noise
        assert filtered_extremes < original_extremes

    @pytest.mark.integration
    def test_document_enhancement_pipeline(self):
        """Test a pipeline designed to enhance document readability."""
        # Create a low-contrast document-like image
        image = np.ones((200, 200), dtype=np.uint8) * 200  # Light gray background
        # Add faint text-like features
        image[50:60, 50:150] = 180  # Faint horizontal line
        image[80:90, 50:150] = 180  # Another faint line
        image[110:120, 50:150] = 180  # Third faint line
        
        processor = ImageProcessor(image)
        # Low contrast before
        contrast_before = image.max() - image.min()
        
        result = processor.process(["denoise", "apply_clahe"])
        
        # Higher contrast after (makes text more visible)
        contrast_after = result.max() - result.min()
        assert contrast_after > contrast_before
        
        # Should enhance the faint features
        assert result.max() > image.max() or result.min() < image.min()

    @pytest.mark.integration  
    def test_binary_document_pipeline(self):
        """Test pipeline for creating binary documents."""
        # Create document-like image with some variation
        image = np.ones((200, 200), dtype=np.uint8) * 250  # Nearly white
        # Add text-like features
        image[50:70, 50:150] = 50   # Dark text
        image[100:120, 50:150] = 50  # More text
        # Add some noise
        noise = np.random.normal(0, 10, (200, 200))
        noisy = np.clip(image + noise, 0, 255).astype(np.uint8)
        
        processor = ImageProcessor(noisy)
        result = processor.process(["apply_bilateral_threshold"])
        
        # Result should be binary
        unique_values = np.unique(result)
        assert len(unique_values) == 2
        assert set(unique_values) == {0, 255}
        
        # Text areas should be preserved
        # Check that some of the text region is black (0)
        text_region = result[50:70, 50:150]
        assert np.sum(text_region == 0) > 0