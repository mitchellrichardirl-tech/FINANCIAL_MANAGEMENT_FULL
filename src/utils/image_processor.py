from dataclasses import dataclass
from email.mime import image
from typing import Optional, Tuple
import logging
import numpy as np
import cv2
from PIL import Image, ImageFilter, ImageEnhance

from src.models.processing_config import ProcessingConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self, image: np.ndarray, config: ProcessingConfig = ProcessingConfig()):
        self.config = config or ProcessingConfig()
        self.original_image = image
        image = self._resize_if_needed(image, self.config)
        self.gray_image = self._convert_to_grayscale(image)
        self.available_methods = {
            "denoise": self._denoise,
            "correct_skew": self._correct_skew,
            "apply_clahe": self._apply_clahe,
            "apply_bilateral_threshold": self._apply_bilateral_threshold,
            "apply_morphological": self._apply_morphological,
        }

    @staticmethod
    def _resize_if_needed(image: np.ndarray, config: ProcessingConfig) -> np.ndarray:
        """Resize image if it exceeds maximum dimensions."""
        height, width = image.shape[:2]
        max_dim = max(height, width)
        
        if max_dim > config.max_dimension:
            scale = config.max_dimension / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            image = cv2.resize(
                image, (new_width, new_height), 
                interpolation=cv2.INTER_AREA
            )
            logger.info(f"Resized from {width}x{height} to {new_width}x{new_height}")
        
        return image
  
    @staticmethod
    def _convert_to_grayscale(image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale if needed."""
        if len(image.shape) == 3:
            # Convert color images to grayscale. OpenCV uses BGR ordering by default.
            if image.shape[2] == 4:
                # Handle images with alpha channel
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            else:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def process(self, methods: Optional[list[str]|str] = None) -> np.ndarray:
        """Process the image using specified methods."""
        if isinstance(methods, str):
            methods = [methods]
        elif methods is None:
            methods = [
                "denoise",
                "correct_skew",
                "apply_clahe",
                "apply_bilateral_threshold",
                "apply_morphological"
            ]

        for method in methods:
            if method not in self.available_methods:
                logger.warning(f"Method {method} is not recognized. Skipping.")
                continue
            process_method = self.available_methods.get(method)
            if callable(process_method):
                logger.info(f"Applying {method}...")
                try:
                    self.gray_image = process_method()
                except Exception as e:
                    logger.error(f"Error applying {method}: {e}")
            else:
                logger.warning(f"Method {method} not found in ImageProcessor.")
        return self.gray_image

    def _denoise(self) -> np.ndarray:
        """Apply advanced denoising."""

        # Denoise
        pil_image = Image.fromarray(self.gray_image)
        pil_image = pil_image.filter(
            ImageFilter.MedianFilter(
                size=self.config.denoise_filter_size
            ))

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(pil_image)
        pil_image = enhancer.enhance(self.config.contrast_factor)
        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(pil_image)
        pil_image = enhancer.enhance(self.config.sharpness_factor)

        self.gray_image = np.array(pil_image)

        return self.gray_image

    def _correct_skew(self) -> np.ndarray:
        """Detect and correct skew using a more robust method."""
        coords = np.column_stack(np.where(self.gray_image > 0))
        
        # Check if we have enough points for minAreaRect
        if len(coords) < 5:  # minAreaRect needs at least 5 points
            logger.warning("Not enough points for skew correction")
            return self.gray_image
        
        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = 90 + angle

        (h, w) = self.gray_image.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        self.gray_image = cv2.warpAffine(
            self.gray_image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        logger.info(f"Corrected skew by {angle:.2f} degrees")
        return self.gray_image
    
    def _apply_clahe(self) -> np.ndarray:
        """Apply Contrast Limited Adaptive Histogram Equalization."""
        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_tile_size
        )
        self.gray_image = clahe.apply(self.gray_image)
        return self.gray_image
    
    def _apply_bilateral_threshold(self) -> np.ndarray:
        """Apply bilateral filter followed by adaptive threshold."""
        bilateral = cv2.bilateralFilter(
            self.gray_image, 
            self.config.bilateral_d,
            self.config.bilateral_sigma_color,
            self.config.bilateral_sigma_space
        )
        self.gray_image = cv2.adaptiveThreshold(
            bilateral, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        return self.gray_image

    def _apply_morphological(self) -> np.ndarray:
        """Apply morphological operations."""
        # First apply bilateral filter
        bilateral = cv2.bilateralFilter(
            self.gray_image, 
            self.config.bilateral_d,
            self.config.bilateral_sigma_color,
            self.config.bilateral_sigma_space
        )
        
        # Morphological closing
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        morph = cv2.morphologyEx(bilateral, cv2.MORPH_CLOSE, kernel)
        
        # Otsu's threshold
        _, self.gray_image = cv2.threshold(morph, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return self.gray_image