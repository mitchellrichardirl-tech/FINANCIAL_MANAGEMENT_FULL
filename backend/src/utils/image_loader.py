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
    """Supported image formats."""
    JPEG = ['.jpg', '.jpeg']
    PNG = ['.png']
    PDF = ['.pdf']
    TIFF = ['.tiff', '.tif']
    BMP = ['.bmp']


class ImageLoader:
    """Handles loading images from various formats."""

    @staticmethod
    def load(file_path: Union[str, Path]) -> List[np.ndarray]:
        """
        Load image(s) from file path.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            List of images as numpy arrays
            
        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file doesn't exist
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
        """Load a single image file."""
        try:
            image = cv2.imread(str(path))
            if image is not None:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                logger.debug(f"Loaded image: {path.name} ({image.shape})")
                return [image]

            # Fallback to PIL
            logger.debug(f"OpenCV failed for {path.name}, trying PIL")
            pil_image = Image.open(path)
            image = np.array(pil_image)
            logger.debug(f"Loaded image via PIL: {path.name} ({image.shape})")
            return [image]

        except Exception as e:
            logger.error(f"Failed to load image {path.name}: {e}")
            raise

    @staticmethod
    def _load_pdf(path: Path) -> List[np.ndarray]:
        """Load all pages from a PDF as images."""
        logger.debug(f"Loading PDF: {path.name}")

        try:
            pil_images = pdf2image.convert_from_path(path)

            images = []
            for i, pil_image in enumerate(pil_images):
                image = np.array(pil_image)
                images.append(image)

            logger.debug(
                f"Loaded PDF {path.name}: {len(images)} pages"
            )
            return images

        except Exception as e:
            logger.error(f"Failed to load PDF {path.name}: {e}")
            raise