"""
Image pre-processing for OCR preparation.

Provides the `ImageProcessor` class, which takes a raw image and
produces multiple independently-processed variants, each using a
different enhancement technique. The OCR extractor downstream tries
all variants and keeps whichever yields the best extraction.

The strategy is "try everything and pick the winner" rather than
"find the one best pre-processing" — receipts vary too much (paper
colour, lighting, crumpling, camera quality) for a single technique
to work universally. Producing several variants is cheap compared to
OCR, so the cost is minimal.

All processing parameters are controlled by `ProcessingConfig`.
"""

from typing import Optional, Dict
import numpy as np
import cv2
from PIL import Image, ImageFilter, ImageEnhance

from src.models.processing_config import ProcessingConfig
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ImageProcessor:
    """Produces multiple pre-processed variants of an image for OCR.

    On construction, the input image is resized (if too large) and
    converted to grayscale. The `process()` method then applies each
    requested technique independently to that grayscale base, returning
    a dict of `{method_name: processed_image}`.

    Available methods:
        - `denoise`: Median filter + contrast/sharpness enhancement.
        - `correct_skew`: Detect and rotate out page tilt.
        - `apply_clahe`: Adaptive histogram equalization.
        - `apply_bilateral_threshold`: Edge-preserving smoothing +
          adaptive binarization.
        - `apply_morphological`: Morphological close + Otsu threshold.

    Attributes:
        config: The `ProcessingConfig` controlling all parameters.
        original_image: The unmodified input image.
        gray_image: Resized, grayscale version used as the base for
            all processing methods.
        available_methods: Dict mapping method names to their
            implementing functions.
    """

    def __init__(self, image: np.ndarray, config: ProcessingConfig = None):
        """Initialize with an image and optional processing config.

        Immediately resizes the image (if it exceeds
        `config.max_dimension`) and converts it to grayscale. These
        steps apply to all methods, so doing them once here avoids
        repetition.

        Args:
            image: Input image as a NumPy array (RGB or RGBA).
            config: Processing parameters. If None, uses
                `ProcessingConfig()` defaults.
        """
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
        """Downscale the image if either dimension exceeds the configured max.

        Preserves aspect ratio. Uses INTER_AREA interpolation, which
        is optimal for downscaling. Upscaling never happens.

        Args:
            image: Input image array.
            config: Config providing `max_dimension`.

        Returns:
            The resized image, or the original if no resizing was
            needed.
        """
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
        """Convert an image to single-channel grayscale.

        Handles RGB (3-channel) and RGBA (4-channel) inputs. Images
        that are already grayscale pass through unchanged.

        Args:
            image: Input image array.

        Returns:
            Single-channel grayscale array (H×W).
        """
        if len(image.shape) == 3:
            if image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
            else:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def process(self, methods: Optional[list[str] | str] = None) -> Dict[str, np.ndarray]:
        """Apply the specified processing methods and return all results.

        Each method is applied independently to a fresh copy of the
        grayscale base image — methods are not chained. Methods that
        fail are logged and skipped without affecting the others.

        Args:
            methods: Method name(s) to apply. Accepts a single string,
                a list of strings, or None for all available methods.
                Unrecognised names are logged and ignored.

        Returns:
            Dict mapping each successfully-applied method name to its
            processed image. May be empty if all methods fail.
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
        """Apply median-filter denoising with contrast and sharpness boost.

        Uses PIL's MedianFilter to remove salt-and-pepper noise, then
        boosts contrast and sharpness. Good for receipts with speckle
        noise or faded print.

        Args:
            image: Grayscale image array.

        Returns:
            Denoised and enhanced image array.
        """
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
        """Detect and rotate out page tilt.

        Finds the minimum-area bounding rectangle of all non-zero
        pixels and uses its orientation to estimate skew angle.
        Rotates to correct if the angle exceeds 0.5°; smaller angles
        are left alone to avoid introducing interpolation artifacts
        for negligible correction.

        Args:
            image: Grayscale image array.

        Returns:
            Deskewed image, or the input unchanged if skew is minimal
            or too few points are available for detection.
        """
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
        """Apply Contrast Limited Adaptive Histogram Equalization.

        Divides the image into tiles and equalizes each independently,
        clipping extreme values to avoid noise amplification. Helps
        with uneven lighting — e.g. receipts photographed under a
        lamp where one side is darker than the other.

        Args:
            image: Grayscale image array.

        Returns:
            CLAHE-equalized image array.
        """
        clahe = cv2.createCLAHE(
            clipLimit=self.config.clahe_clip_limit,
            tileGridSize=self.config.clahe_tile_size
        )
        return clahe.apply(image)

    def _apply_bilateral_threshold(self, image: np.ndarray) -> np.ndarray:
        """Apply bilateral filtering followed by adaptive thresholding.

        Bilateral filter smooths noise while preserving text edges,
        then adaptive Gaussian threshold binarizes. Good for receipts
        with textured or off-white backgrounds.

        Args:
            image: Grayscale image array.

        Returns:
            Binary (black/white) image array.
        """
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
        """Apply morphological closing followed by Otsu's threshold.

        Bilateral filter first for edge-preserving denoising, then a
        morphological close (dilate → erode) to fill small gaps in
        characters, then Otsu's global threshold. Effective for
        dot-matrix or thermal receipts where characters have broken
        strokes.

        Args:
            image: Grayscale image array.

        Returns:
            Binary (black/white) image array.
        """
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