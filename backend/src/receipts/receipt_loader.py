"""
Receipt image loading and pre-processing.

Provides the `ReceiptLoader` class, which takes one or more image files
(JPEG, PNG, PDF, etc.), splits multi-page documents into individual
images, runs each through the image pre-processing pipeline, and yields
`Receipt` objects with the original and processed images populated.

This is the first stage of the receipt pipeline:

    ReceiptLoader → Receipt(original_image, processed_images)
        → ReceiptExtractor (OCR + field parsing)
            → ReceiptRepository (database persistence)

Supports both eager (list) and lazy (iterator) modes to control memory
usage when processing large batches.
"""

from typing import List, Optional, Iterator, Union
from pathlib import Path

from src.utils.image_loader import ImageLoader
from src.utils.image_processor import ImageProcessor
from src.models.receipt import Receipt
from src.models.processing_config import ProcessingConfig
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class ReceiptLoader:
    """Loads receipt images from disk and runs them through pre-processing.

    Handles single-page images and multi-page documents (e.g. PDFs)
    transparently — each page becomes one `Receipt` object. Delegates
    image loading to `ImageLoader` and per-image processing to
    `ImageProcessor`.

    Attributes:
        processing_config: The `ProcessingConfig` controlling image
            pre-processing parameters.
        image_loader: `ImageLoader` instance used to read files from
            disk and split multi-page documents.
    """

    def __init__(self, processing_config: Optional[ProcessingConfig] = None):
        """Initialize with an optional custom processing configuration.

        Args:
            processing_config: Image pre-processing parameters. If None,
                uses `ProcessingConfig()` defaults.
        """
        self.processing_config = processing_config or ProcessingConfig()
        self.image_loader = ImageLoader()
        logger.debug("Initialized ReceiptLoader")

    def process_file(
        self,
        file_path: Union[str, Path],
        yield_pages: bool = False
    ) -> Union[List[Receipt], Iterator[Receipt]]:
        """Load and pre-process a single receipt file.

        For multi-page files (e.g. PDFs), each page produces a separate
        `Receipt`. Pages that fail processing are logged and skipped.

        Args:
            file_path: Path to the image or PDF file.
            yield_pages: If True, return a lazy iterator to keep memory
                usage low. If False (default), return a fully
                materialized list.

        Returns:
            List or iterator of `Receipt` objects, each with
            `original_image` and `processed_images` populated.
        """
        file_path = Path(file_path)

        if yield_pages:
            return self._process_file_lazy(file_path)
        return list(self._process_file_lazy(file_path))

    def _process_file_lazy(self, file_path: Path) -> Iterator[Receipt]:
        """Process a single file lazily, yielding one `Receipt` per page.

        Loads all pages into memory via `ImageLoader`, then processes
        them one at a time. Individual page failures are logged and
        skipped — they do not abort the remaining pages.

        Args:
            file_path: Resolved path to the file.

        Yields:
            A `Receipt` for each successfully processed page, with
            `original_filename`, `page_number`, `original_image`, and
            `processed_images` populated.
        """
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
        """Load and pre-process one or more receipt files.

        Convenience wrapper that accepts a single path or a list.
        Iterates through files in order, delegating each to
        `process_file()`. Files that fail entirely (e.g. unreadable)
        are logged and skipped.

        Args:
            file_paths: Single path or list of paths to receipt files.
            yield_pages: If True, return a lazy iterator across all
                pages of all files. If False (default), return a
                materialized list.

        Returns:
            List or iterator of `Receipt` objects from all files.
        """
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
        """Process multiple files lazily, yielding `Receipt` objects.

        Iterates through files sequentially. If a file fails entirely
        (e.g. `ImageLoader` raises), it is logged and skipped —
        remaining files are still processed.

        Args:
            file_paths: List of paths to process.
            n_files: Total count (pre-computed, for logging).

        Yields:
            `Receipt` objects from all files, in file-order then
            page-order.
        """
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