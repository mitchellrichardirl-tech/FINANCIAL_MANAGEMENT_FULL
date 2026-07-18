import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple
import asyncio

from src.api.services.parallel_processor import (
    ParallelStreamProcessor,
    ProcessingTask,
    ProcessingResult,
)
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)

def receipt_worker(args: Tuple) -> ProcessingResult:
    """Sync worker for the multiprocessing (OCR/Regex) path."""
    (index, identifier, temp_path, upload_folder_path, _allowed_extensions) = args
    from src.receipts.receipt_extractor import ReceiptExtractor
    from src.database.repositories.receipts import ReceiptRepository
    from src.receipts import worker_common as wc
    try:
        pages = wc.load_pages(temp_path)
        if not pages:
            return wc.failure(index, identifier, "Unable to process image")
        extractor = ReceiptExtractor()
        receipt = wc.select_best([extractor.process_receipt(p) for p in pages])
        receipt_id, stored_filename = wc.persist(
            temp_path, identifier, upload_folder_path,
            receipt, ReceiptRepository(),
        )
        if receipt_id is None:
            return wc.failure(index, identifier, "Failed to save to database")
        return wc.success(index, identifier, receipt_id, receipt, stored_filename)
    except Exception as e:
        return wc.failure(index, identifier, str(e))

async def receipt_worker_async(
    task: ProcessingTask,
    upload_folder: str,
    extractor,      # shared MultimodalExtractor instance
    repository,     # shared repository (connection-per-save, so thread-safe)
) -> ProcessingResult:
    """Async worker for the multimodal (Gemini) path."""
    from src.receipts import worker_common as wc
    index, identifier, temp_path = task.index, task.identifier, task.data
    try:
        pages = await asyncio.to_thread(wc.load_pages, temp_path)
        if not pages:
            return wc.failure(index, identifier, "Unable to process image")
        processed = await asyncio.gather(
            *(extractor.aprocess_receipt(p) for p in pages)
        )
        receipt = wc.select_best(list(processed))
        receipt_id, stored_filename = await asyncio.to_thread(
            wc.persist, temp_path, identifier, upload_folder,
            receipt, repository,
        )
        if receipt_id is None:
            return wc.failure(index, identifier, "Failed to save to database")
        return wc.success(index, identifier, receipt_id, receipt, stored_filename)
    except Exception as e:
        return wc.failure(index, identifier, str(e))

class ReceiptStreamProcessor:
    """Handles streaming receipt processing with parallel execution."""

    def __init__(
        self,
        upload_folder: Path,
        allowed_extensions: Set[str],
        max_workers: Optional[int] = None
    ):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        self._processor = ParallelStreamProcessor(
            worker_function=receipt_worker,
            max_workers=max_workers
        )
        logger.debug(
            f"Initialized with upload_folder={upload_folder}, "
            f"allowed_extensions={allowed_extensions}"
        )

    def process_files(
        self,
        temp_files: List[Tuple[str, str]],
        form_data: Optional[Dict] = None
    ) -> Generator[str, None, None]:
        """
        Process files and yield SSE events.
        
        Args:
            temp_files: List of (original_filename, temp_path) tuples
            form_data: Optional form data for overrides (not currently used)
            
        Yields:
            SSE event strings
        """
        logger.info(f"Processing {len(temp_files)} receipt files")

        if form_data:
            logger.debug(f"Form data provided (unused): {list(form_data.keys())}")

        # Convert to ProcessingTask objects
        tasks = [
            ProcessingTask(
                index=index,
                identifier=filename,
                data=temp_path
            )
            for index, (filename, temp_path) in enumerate(temp_files)
        ]

        # Extra args passed to worker: (upload_folder, allowed_extensions)
        extra_args = (str(self.upload_folder), self.allowed_extensions)

        yield from self._processor.process(tasks, extra_worker_args=extra_args)