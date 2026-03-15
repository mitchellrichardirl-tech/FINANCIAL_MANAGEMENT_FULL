from typing import List, Optional, Iterator, Union
from pathlib import Path

from src.utils.image_loader import ImageLoader
from src.utils.image_processor import ImageProcessor
from src.models.receipt import Receipt
from src.models.processing_config import ProcessingConfig
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ReceiptLoader:
    """Loads receipt images and processes them into Receipt objects."""

    def __init__(self, processing_config: Optional[ProcessingConfig] = None):
        self.processing_config = processing_config or ProcessingConfig()
        self.image_loader = ImageLoader()
        logger.debug("Initialized ReceiptLoader")

    def process_file(
        self,
        file_path: Union[str, Path],
        yield_pages: bool = False
    ) -> Union[List[Receipt], Iterator[Receipt]]:
        """Process a single receipt file."""
        file_path = Path(file_path)

        if yield_pages:
            return self._process_file_lazy(file_path)
        return list(self._process_file_lazy(file_path))

    def _process_file_lazy(self, file_path: Path) -> Iterator[Receipt]:
        """Process a single file lazily, yielding one Receipt per page."""
        logger.info(f"Loading receipt file: {file_path.name}")

        images = self.image_loader.load(file_path)
        n_images = len(images)
        logger.debug(f"Loaded {n_images} image(s) from {file_path.name}")

        processed = 0
        failed = 0

        for i, img in enumerate(images):
            try:
                logger.debug(
                    f"Processing image {i + 1}/{n_images}: {file_path.name}"
                )
                processor = ImageProcessor(img, config=self.processing_config)
                processed_imgs = processor.process()
                processed += 1

                yield Receipt(
                    original_filename=file_path,
                    page_number=i,
                    original_image=img,
                    processed_images=processed_imgs
                )
            except Exception as e:
                failed += 1
                logger.error(
                    f"Failed to process image {i + 1}/{n_images} "
                    f"from {file_path.name}: {e}"
                )
                continue

        if failed > 0:
            logger.warning(
                f"File {file_path.name}: {processed}/{n_images} succeeded, "
                f"{failed} failed"
            )

    def process_files(
        self,
        file_paths: Union[str, Path, List[Union[str, Path]]],
        yield_pages: bool = False
    ) -> Union[List[Receipt], Iterator[Receipt]]:
        """Process one or more receipt files."""
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
        """Process multiple files lazily."""
        for i, file_path in enumerate(file_paths):
            file_path = Path(file_path)
            logger.debug(f"Processing file {i + 1}/{n_files}: {file_path.name}")

            try:
                yield from self._process_file_lazy(file_path)
            except Exception as e:
                logger.error(
                    f"Skipping file {i + 1}/{n_files} ({file_path.name}): {e}"
                )
                continue

        logger.debug(f"Completed processing {n_files} files")