"""
Multi-format image loading for the receipt pipeline.

Provides `ImageLoader`, which reads image files (JPEG, PNG, TIFF, BMP)
and multi-page PDFs into NumPy arrays suitable for the image processing
and OCR stages. Handles format detection, PDF page splitting, and
OpenCV/PIL fallback.

All images are returned in RGB channel order regardless of the source
format.
"""

from PIL import Image
import cv2
import numpy as np
import pdf2image
from pathlib import Path
from typing import List, Union
from enum import Enum

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ImageFormat(Enum):
    """Supported image file formats, mapped to their file extensions.

    Used by `ImageLoader.load()` to determine how to read a file.
    PDF is handled separately from raster formats because it requires
    page-level conversion.

    Members:
        JPEG: `.jpg`, `.jpeg`
        PNG: `.png`
        PDF: `.pdf` (multi-page supported)
        TIFF: `.tiff`, `.tif`
        BMP: `.bmp`
    """
    JPEG = ['.jpg', '.jpeg']
    PNG = ['.png']
    PDF = ['.pdf']
    TIFF = ['.tiff', '.tif']
    BMP = ['.bmp']


class ImageLoader:
    """Loads images from disk into NumPy arrays.

    Supports single-page raster formats and multi-page PDFs. Each page
    becomes one array in the returned list, so callers always get a
    uniform `List[np.ndarray]` regardless of input format.

    All methods are static — no instance state is needed.
    """

    @staticmethod
    def load(file_path: Union[str, Path]) -> List[np.ndarray]:
        """Load one or more images from a file.

        Detects format from the file extension and delegates to the
        appropriate loader. PDFs are converted page-by-page; all other
        supported formats produce a single-element list.

        Args:
            file_path: Path to the image or PDF file.

        Returns:
            List of images as NumPy arrays in RGB channel order
            (H×W×C). One element per page/image.

        Raises:
            FileNotFoundError: If `file_path` does not exist.
            ValueError: If the file extension is not recognised.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extension = path.suffix.lower()

        if extension in ImageFormat.PDF.value:
            return ImageLoader._load_pdf(path)

        for format_type in ImageFormat:
            if extension in format_type.value:
                return ImageLoader._load_image(path)

        logger.warning(f"Unsupported image format: {extension}")
        raise ValueError(f"Unsupported file format: {extension}")

    @staticmethod
    def _load_image(path: Path) -> List[np.ndarray]:
        """Load a single raster image file.

        Tries OpenCV first (faster), then falls back to PIL if OpenCV
        returns None (which can happen with uncommon colour profiles
        or file quirks). The result is converted to RGB in either case.

        Args:
            path: Resolved path to the image file.

        Returns:
            Single-element list containing the image as an RGB NumPy
            array.

        Raises:
            Exception: If both OpenCV and PIL fail to load the file.
        """
        try:
            image = cv2.imread(str(path))
            if image is not None:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                logger.debug(f"Loaded image: {path.name} ({image.shape})")
                return [image]

            # Fallback to PIL
            logger.debug(f"OpenCV failed for {path.name}, trying PIL")
            pil_image = Image.open(path).convert('RGB')
            image = np.array(pil_image)
            logger.debug(f"Loaded image via PIL: {path.name} ({image.shape})")
            return [image]

        except Exception as e:
            logger.error(f"Failed to load image {path.name}: {e}")
            raise

    @staticmethod
    def _load_pdf(path: Path) -> List[np.ndarray]:
        """Convert each page of a PDF to an RGB image.

        Uses `pdf2image` (Poppler-based) for conversion. Each page is
        rendered at the library's default DPI and returned as a NumPy
        array.

        Args:
            path: Resolved path to the PDF file.

        Returns:
            List of RGB NumPy arrays, one per page. Empty PDFs return
            an empty list.

        Raises:
            Exception: If `pdf2image` fails (e.g. Poppler not installed,
                corrupted PDF).
        """
        logger.debug(f"Loading PDF: {path.name}")

        try:
            pil_images = pdf2image.convert_from_path(path)

            images = []
            for i, pil_image in enumerate(pil_images):
                image = np.array(pil_image.convert('RGB'))
                images.append(image)

            logger.debug(
                f"Loaded PDF {path.name}: {len(images)} pages"
            )
            return images

        except Exception as e:
            logger.error(f"Failed to load PDF {path.name}: {e}")
            raise