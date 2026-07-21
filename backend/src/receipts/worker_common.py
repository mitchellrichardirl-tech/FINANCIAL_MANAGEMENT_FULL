import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from src.api.services.parallel_processor import ProcessingResult
from src.models.receipt import Receipt

def load_pages(
        temp_path: str,
        apply_methods: Optional[bool]=True
        ) -> List[Receipt]:
    # Deferred import: safe inside multiprocessing workers
    from src.receipts.receipt_loader import ReceiptLoader
    return list(ReceiptLoader().process_files(
        Path(temp_path),
        yield_pages=True,
        apply_methods=apply_methods
        ))

def select_best(processed: List[Receipt]) -> Receipt:
    """Best-confidence page; works for single-page lists too."""
    return max(processed, key=lambda r: getattr(r, "confidence", None) or 0.0)

def build_storage_path(identifier: str, upload_folder: str) -> Tuple[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(identifier)
    stored_filename = f"receipt_{timestamp}_{name}_{uuid.uuid4().hex[:8]}{ext}"
    return stored_filename, Path(upload_folder) / stored_filename

def cleanup_stored_file(stored_path: Optional[Path]) -> None:
    if stored_path and Path(stored_path).exists():
        Path(stored_path).unlink()

def persist(
    temp_path: str,
    identifier: str,
    upload_folder: str,
    receipt: Receipt,
    repository,
) -> Tuple[Optional[int], str]:
    """
    Copy to permanent storage, attach metadata, save to DB.
    Owns its own rollback: the stored file is removed on any failure,
    whether save() returns None or an exception is raised.
    Returns (receipt_id_or_None, stored_filename).
    """
    stored_filename, stored_path = build_storage_path(identifier, upload_folder)
    try:
        shutil.copy2(temp_path, stored_path)
        receipt.original_filename = identifier
        receipt.stored_filename = stored_filename
        receipt.file_path = stored_path
        receipt_id = repository.save(receipt)
        if receipt_id is None:
            cleanup_stored_file(stored_path)
        return receipt_id, stored_filename
    except Exception:
        cleanup_stored_file(stored_path)
        raise

def failure(index: int, identifier: str, error: str) -> ProcessingResult:
    return ProcessingResult(index=index, identifier=identifier,
                            success=False, error=error)
                            
def success(
    index: int, identifier: str, receipt_id: int,
    receipt: Receipt, stored_filename: str,
) -> ProcessingResult:
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
                "confidence": getattr(receipt, "confidence", None),
            },
            "stored_filename": stored_filename,
        },
    )