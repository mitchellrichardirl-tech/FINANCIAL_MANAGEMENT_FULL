import numpy as np
from typing import List, Optional, Iterator, Union
import logging
from pathlib import Path

from src.utils.image_loader import ImageLoader
from src.utils.image_processor import ImageProcessor
from src.models.receipt import Receipt
from src.models.processing_config import ProcessingConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReceiptLoader:
    def __init__(self, processing_config: Optional[ProcessingConfig] = None):
        self.processing_config = processing_config or ProcessingConfig()
        self.image_loader = ImageLoader()

    def process_file(
            self,
            file_path: Union[str, Path],
            yield_pages: bool = False
            ) -> Union[List[Receipt], Iterator[Receipt]]:
        file_path = Path(file_path)
        logger.info(f"Loading receipt file: {file_path}")

        if yield_pages:
            return self._process_file_lazy(file_path)
        return list(self._process_file_lazy(file_path))
    
    def _process_file_lazy(self, file_path: Path) -> Iterator[Receipt]:
        logger.info(f"Loading receipt file: {file_path}")
        images = self.image_loader.load(file_path)
        n_images = len(images)
        logger.info(f"Loaded {n_images} image(s) from {file_path}")
        for i, img in enumerate(images):
            try:
                logger.info(f"Processing image {i+1} of {n_images} from {file_path}")
                processor = ImageProcessor(img, config=self.processing_config)
                processed_imgs = processor.process()
                logger.info(f"Processed image {i+1} of {n_images} from {file_path}")
                yield Receipt(
                    source_file=file_path,
                    page_number=i,
                    original_image=img,
                    processed_images=processed_imgs
                    )
            except Exception as e:
                logger.error(f"Error processing image {i+1} of {n_images} from {file_path}: {e}")
                continue
        
    def process_files(
            self,
            file_paths: Union[str, Path, List[Union[str, Path]]],
            yield_pages: bool = False
            ) -> Union[List[Receipt], Iterator[Receipt]]:
        if isinstance(file_paths, (str, Path)):
            file_paths = [file_paths]
        n_files = len(file_paths)
        logger.info(f"Processing {n_files} receipt file(s)")
        if yield_pages:
            return self._process_files_lazy(file_paths, n_files)
        return list(self._process_files_lazy(file_paths, n_files))
    
    def _process_files_lazy(
            self,
            file_paths: List[Union[str, Path]],
            n_files: int
            ) -> Iterator[Receipt]:
        for i, file_path in enumerate(file_paths):
            file_path = Path(file_path)
            logger.info(f"Processing file: {file_path}; file {i+1} of {n_files}")
            try:
                yield from self._process_file_lazy(file_path)
            except Exception as e:
                logger.error(f"Skipping file {file_path}; {i+1} of {n_files} due to error: {e}")
                continue
        
if __name__ == "__main__":
    # Example usage
    test_receipt_paths = [
        "/workspaces/financial_management/data/250804 sebbie helmet.jpg"
    ]
    receipt_loader = ReceiptLoader()
    processed_images = receipt_loader.process_files(test_receipt_paths, yield_pages=True)
    for rcpt in processed_images:
        logger.info(f"Receipt from {rcpt.source_file}, page {rcpt.page_number}, "
                    f"original shape: {rcpt.original_image.shape}, "
                    f"processed shape: {rcpt.processed_images.shape}")