from PIL import Image
import cv2
import numpy as np
import pdf2image
from pathlib import Path
from typing import List, Union
import logging
from enum import Enum
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Load image(s) from file path.
        
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
        
        # Check PDF
        if extension in ImageFormat.PDF.value:
            return ImageLoader._load_pdf(path)
        
        # Check standard image formats
        for format_type in ImageFormat:
            if extension in format_type.value:
                return ImageLoader._load_image(path)
        
        raise ValueError(f"Unsupported file format: {extension}")
    
    @staticmethod
    def _load_image(path: Path) -> List[np.ndarray]:
        """Load a single image file."""
        try:
            # Try OpenCV first (handles more formats)
            image = cv2.imread(str(path))
            if image is not None:
                # Convert BGR to RGB for consistency
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                logger.info(f"Loaded image: {path.name} {image.shape}")
                return [image]
            
            # Fallback to PIL
            pil_image = Image.open(path)
            image = np.array(pil_image)
            logger.info(f"Loaded image with PIL: {path.name} {image.shape}")
            return [image]
            
        except Exception as e:
            logger.error(f"Failed to load image {path}: {e}")
            raise
    
    @staticmethod
    def _load_pdf(path: Path) -> List[np.ndarray]:
        """Load all pages from a PDF as images."""
        logger.info(f"Loading PDF: {path.name}")
        try:
            images = []
            pil_images = pdf2image.convert_from_path(path)
            
            logger.info(f"Number of pages in PDF: {len(pil_images)}")
            for i, pil_image in enumerate(pil_images):
                image = np.array(pil_image)
                images.append(image)
                logger.info(f"Loaded PDF page {i+1}/{len(pil_images)}: {image.shape}")
            
            return images
            
        except Exception as e:
            logger.error(f"Failed to load PDF {path}: {e}")
            raise

if __name__ == "__main__":
    # Example usage
    test_image_path = "/workspaces/financial_management/data/250804 sebbie helmet.jpg"
    try:
        images = ImageLoader.load(test_image_path)
        for idx, img in enumerate(images):
            logger.info(f"Image {idx+1} shape: {img.shape}")
    except Exception as e:
        logger.error(f"Error loading images: {e}")