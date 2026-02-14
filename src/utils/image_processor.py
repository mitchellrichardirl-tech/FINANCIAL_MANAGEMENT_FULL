from typing import Optional, Dict
import numpy as np
import cv2
from PIL import Image, ImageFilter, ImageEnhance

from src.models.processing_config import ProcessingConfig
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ImageProcessor:
   """Applies various image processing techniques for OCR preparation."""

   def __init__(self, image: np.ndarray, config: ProcessingConfig = None):
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
           logger.debug(
               f"Resized image: {width}x{height} -> {new_width}x{new_height}"
           )

       return image

   @staticmethod
   def _convert_to_grayscale(image: np.ndarray) -> np.ndarray:
       """Convert image to grayscale if needed."""
       if len(image.shape) == 3:
           if image.shape[2] == 4:
               image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
           else:
               image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
       return image

   def process(self, methods: Optional[list[str] | str] = None) -> Dict[str, np.ndarray]:
       """
       Process the image using specified methods.
       
       Each method is applied independently to the base grayscale image.
       
       Args:
           methods: List of method names or single method name to apply.
                   If None, applies all available methods.
       
       Returns:
           Dictionary with method names as keys and processed images as values.
       """
       if isinstance(methods, str):
           methods = [methods]
       elif methods is None:
           methods = list(self.available_methods.keys())

       logger.debug(f"Processing image with methods: {methods}")

       processed_images = {}
       successful = 0
       failed = 0

       for method in methods:
           if method not in self.available_methods:
               logger.warning(f"Unknown processing method: {method}")
               continue

           process_method = self.available_methods[method]
           try:
               processed_images[method] = process_method(self.gray_image.copy())
               successful += 1
           except Exception as e:
               logger.error(f"Processing method '{method}' failed: {e}")
               failed += 1

       if failed > 0:
           logger.warning(
               f"Image processing: {successful}/{successful + failed} methods succeeded"
           )

       return processed_images

   def _denoise(self, image: np.ndarray) -> np.ndarray:
       """Apply advanced denoising with contrast and sharpness enhancement."""
       pil_image = Image.fromarray(image)
       pil_image = pil_image.filter(
           ImageFilter.MedianFilter(size=self.config.denoise_filter_size)
       )

       enhancer = ImageEnhance.Contrast(pil_image)
       pil_image = enhancer.enhance(self.config.contrast_factor)

       enhancer = ImageEnhance.Sharpness(pil_image)
       pil_image = enhancer.enhance(self.config.sharpness_factor)

       return np.array(pil_image)

   def _correct_skew(self, image: np.ndarray) -> np.ndarray:
       """Detect and correct image skew."""
       coords = np.column_stack(np.where(image > 0))

       if len(coords) < 5:
           logger.debug("Insufficient points for skew correction")
           return image

       angle = cv2.minAreaRect(coords)[-1]

       if angle < -45:
           angle = 90 + angle

       if abs(angle) < 0.5:
           logger.debug(f"Skew angle {angle:.2f}° below threshold, skipping")
           return image

       (h, w) = image.shape[:2]
       center = (w // 2, h // 2)
       rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
       rotated_image = cv2.warpAffine(
           image, rotation_matrix, (w, h),
           flags=cv2.INTER_CUBIC,
           borderMode=cv2.BORDER_REPLICATE
       )

       logger.debug(f"Corrected skew: {angle:.2f}°")
       return rotated_image

   def _apply_clahe(self, image: np.ndarray) -> np.ndarray:
       """Apply Contrast Limited Adaptive Histogram Equalization."""
       clahe = cv2.createCLAHE(
           clipLimit=self.config.clahe_clip_limit,
           tileGridSize=self.config.clahe_tile_size
       )
       return clahe.apply(image)

   def _apply_bilateral_threshold(self, image: np.ndarray) -> np.ndarray:
       """Apply bilateral filter followed by adaptive threshold."""
       bilateral = cv2.bilateralFilter(
           image,
           self.config.bilateral_d,
           self.config.bilateral_sigma_color,
           self.config.bilateral_sigma_space
       )
       thresholded = cv2.adaptiveThreshold(
           bilateral, 255,
           cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
           cv2.THRESH_BINARY, 11, 2
       )
       return thresholded

   def _apply_morphological(self, image: np.ndarray) -> np.ndarray:
       """Apply morphological operations with Otsu's threshold."""
       bilateral = cv2.bilateralFilter(
           image,
           self.config.bilateral_d,
           self.config.bilateral_sigma_color,
           self.config.bilateral_sigma_space
       )

       kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
       morph = cv2.morphologyEx(bilateral, cv2.MORPH_CLOSE, kernel)

       _, thresholded = cv2.threshold(
           morph, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
       )

       return thresholded