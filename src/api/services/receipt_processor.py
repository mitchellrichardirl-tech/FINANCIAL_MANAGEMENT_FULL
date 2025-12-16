import os
import uuid
import shutil
import logging
import multiprocessing
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.api.utils.sse import SSEEventBuilder, ProgressInfo

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result from processing a single task."""
    index: int
    identifier: str
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


def get_optimal_workers(max_workers: Optional[int] = None, cpu_limit: int = 4) -> int:
    """Calculate optimal number of workers."""
    if max_workers is not None:
        return max_workers
    return min(cpu_limit, multiprocessing.cpu_count())


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
        self.max_workers = get_optimal_workers(max_workers)
    
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
        total = len(temp_files)
        processed_count = 0
        
        yield SSEEventBuilder.starting(total, workers=self.max_workers)
        
        worker_args = [
            (index, filename, temp_path, str(self.upload_folder), self.allowed_extensions)
            for index, (filename, temp_path) in enumerate(temp_files)
        ]
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_info = {}
            
            for args in worker_args:
                index, filename = args[0], args[1]
                
                yield SSEEventBuilder.processing(
                    index=index,
                    identifier=filename,
                    progress=ProgressInfo(processed_count, total),
                    message="Queued for processing..."
                )
                
                future = executor.submit(receipt_worker, args)
                future_to_info[future] = (index, filename)
            
            for future in as_completed(future_to_info):
                index, filename = future_to_info[future]
                
                try:
                    result: ProcessingResult = future.result()
                    processed_count += 1
                    progress = ProgressInfo(processed_count, total)
                    
                    if result.success:
                        yield SSEEventBuilder.success(
                            index=result.index,
                            identifier=result.identifier,
                            result_data=result.data or {},
                            progress=progress
                        )
                    else:
                        yield SSEEventBuilder.error(
                            index=result.index,
                            identifier=result.identifier,
                            error_message=result.error or "Unknown error",
                            progress=progress
                        )
                        
                except Exception as e:
                    processed_count += 1
                    logger.error(f"Worker error for {filename}: {e}")
                    
                    yield SSEEventBuilder.error(
                        index=index,
                        identifier=filename,
                        error_message=f"Processing failed: {str(e)}",
                        progress=ProgressInfo(processed_count, total)
                    )
        
        yield SSEEventBuilder.completed(processed_count)