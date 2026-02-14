import os
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple

from src.api.services.parallel_processor import (
    ParallelStreamProcessor,
    ProcessingTask,
    ProcessingResult,
)
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def receipt_worker(args: Tuple) -> ProcessingResult:
    """
    Worker function for processing a single receipt.
    
    Runs in a separate process - imports are done here to avoid pickling issues.
    """
    (index, identifier, temp_path, upload_folder_path, _allowed_extensions) = args

    # Import in worker process
    from src.receipts.receipt_extractor import ReceiptExtractor
    from src.receipts.receipt_loader import ReceiptLoader
    from src.database.repositories.receipts import ReceiptRepository

    extractor = ReceiptExtractor()
    loader = ReceiptLoader()
    repository = ReceiptRepository()

    stored_path = None

    try:
        # Load and process
        receipts = list(loader.process_files(Path(temp_path), yield_pages=True))

        if not receipts:
            return ProcessingResult(
                index=index,
                identifier=identifier,
                success=False,
                error="Unable to process image"
            )

        # Process - take best confidence for multi-page
        if len(receipts) > 1:
            processed = [extractor.process_receipt(r) for r in receipts]
            receipt = max(processed, key=lambda r: r.confidence)
        else:
            receipt = extractor.process_receipt(receipts[0])

        # Generate stored filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(identifier)
        random_suffix = uuid.uuid4().hex[:8]
        stored_filename = f"receipt_{timestamp}_{name}_{random_suffix}{ext}"

        # Copy to permanent storage
        stored_path = Path(upload_folder_path) / stored_filename
        shutil.copy2(temp_path, stored_path)

        # Update receipt and save
        receipt.original_filename = identifier
        receipt.stored_filename = stored_filename
        receipt.file_path = stored_path

        receipt_id = repository.save(receipt)

        if receipt_id is None:
            if stored_path and stored_path.exists():
                stored_path.unlink()
            return ProcessingResult(
                index=index,
                identifier=identifier,
                success=False,
                error="Failed to save to database"
            )

        return ProcessingResult(
            index=index,
            identifier=identifier,
            success=True,
            data={
                "receipt_id": receipt_id,
                "extracted_data": {
                    "vendor": receipt.vendor,
                    "amount": receipt.amount,
                    "date": receipt.date.isoformat() if receipt.date else None,
                    "confidence": getattr(receipt, 'confidence', None)
                },
                "stored_filename": stored_filename
            }
        )

    except Exception as e:
        if stored_path and Path(stored_path).exists():
            stored_path.unlink()

        return ProcessingResult(
            index=index,
            identifier=identifier,
            success=False,
            error=str(e)
        )


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