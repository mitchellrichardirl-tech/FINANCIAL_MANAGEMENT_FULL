"""
Data model for a receipt image and its extracted data.

A `Receipt` instance tracks a single receipt through the full
processing pipeline: raw image → pre-processed images → OCR text →
structured fields (vendor, date, amount). It starts with only
`original_filename` and `page_number` populated, and accumulates
data as each pipeline stage runs.
"""

import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, Any
from datetime import datetime
from pathlib import Path


@dataclass
class Receipt:
    """A receipt image and the data extracted from it.

    Serves as the working state object passed through the receipt
    processing pipeline. Fields are populated progressively:

        1. Construction: `original_filename`, `page_number`.
        2. Image loading: `original_image`.
        3. Pre-processing: `processed_images`.
        4. OCR extraction: `extracted_text`, `selected_method`,
           `confidence`.
        5. Field parsing: `vendor`, `date`, `amount`.
        6. Storage: `stored_filename`, `file_path`.

    Also used by `ReceiptRepository.save()` as the input format for
    database persistence.

    Attributes:
        original_filename: Name of the uploaded file (may be a
            multi-page PDF, in which case `page_number` identifies
            the specific page).
        page_number: Zero-based page index within the source file.
            Always 0 for single-image uploads.
        original_image: Raw image as a NumPy array (H×W×C), or None
            if not yet loaded.
        processed_images: Dict of processing-method names to their
            resulting images. Populated by the image processor so
            multiple OCR strategies can be tried.
        extracted_text: Raw OCR output from the selected method.
        selected_method: Name of the OCR/processing method that
            produced the best result (e.g. "enhanced", "bilateral").
        confidence: Extraction confidence score. Interpretation
            depends on the extraction method; stored as 0–3 integer
            in the database.
        vendor: Extracted merchant/vendor name.
        date: Extracted receipt date.
        amount: Extracted total amount.
        stored_filename: Deduplicated filename used for on-disk
            storage. Set after the file is saved to the uploads
            directory.
        file_path: Full filesystem path to the stored image. Set
            alongside `stored_filename`.
    """
    original_filename: Path
    page_number: int
    original_image: np.ndarray | None = None
    processed_images: Dict[str, np.ndarray] | None = None
    extracted_text: str | None = None
    selected_method: str | None = None
    confidence: float | None = None
    vendor: str | None = None
    date: datetime | None = None
    amount: float | None = None
    stored_filename: str | None = None
    file_path: Path | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict via `dataclasses.asdict()`.

        Note:
            NumPy arrays (`original_image`, `processed_images`) are
            included as-is and are not JSON-serializable. Use
            `ReceiptRepository.save()` for database persistence, which
            only writes the scalar fields.
        """
        return asdict(self)