"""
Abstract contracts for the receipt extraction pipeline.

Defines three abstractions that let multiple OCR engines and field
extractors coexist behind stable interfaces:

    OCREngine          image  -> text
    FieldExtractor     text   -> ExtractedFields
    ReceiptExtractorBase  Receipt -> Receipt   (composes the above)

Concrete implementations live as siblings under engines/ and
field_extractors/. This allows A/B benchmarking and incremental
migration without disturbing the loader or repository layers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

import numpy as np

from src.models.receipt import Receipt
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


@dataclass
class ExtractedFields:
    """Result of field extraction, independent of source method.

    Attributes:
        vendor: Merchant name, or None.
        amount: Final total paid, or None.
        date: Purchase date, or None.
    """
    vendor: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[datetime] = None

    @property
    def confidence(self) -> int:
        """0–3 count of populated fields (preserves legacy semantics)."""
        return sum(
            [self.vendor is not None,
             self.amount is not None,
             self.date is not None]
        )


class OCREngine(ABC):
    """Converts an image into plain text.

    Implementations must be safe to construct once and reuse across
    many images (model loading is expensive).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in logs and benchmark reports."""

    @abstractmethod
    def extract_text(self, image: np.ndarray) -> str:
        """Return OCR text for a single image, '' on failure."""


class FieldExtractor(ABC):
    """Parses structured fields out of OCR text."""
    def __init__(self, name: Optional[str] = None):
        self.my_name = name

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in logs and benchmark reports."""

    @abstractmethod
    def extract(self, text: str) -> ExtractedFields:
        """Return structured fields from OCR text."""


class ReceiptExtractorBase(ABC):
    """Orchestrates OCR + field extraction over a Receipt's variants.

    Provides a single template method, `process_receipt`, shared by all
    pipelines. Subclasses supply an `OCREngine` and a `FieldExtractor`
    plus a variant-selection policy.

    The public contract is unchanged from the original extractor:
    `process_receipt(receipt)` mutates and returns the same Receipt,
    populating vendor, amount, date, extracted_text, selected_method,
    and confidence.
    """

    def __init__(self, ocr: OCREngine, fields: FieldExtractor):
        self.ocr = ocr
        self.fields = fields
        self.last_ocr_text: Optional[str] = None
        self.my_name: Optional[str] = None  # overridable for benchmark reports

    @property
    def name(self) -> str:
        """Composite identifier, e.g. 'paddle+llm'."""
        if self.my_name:
            return self.my_name
        return f"{self.ocr.name}+{self.fields.name}"

    @abstractmethod
    def _select_variants(self, receipt: Receipt) -> list[str]:
        """Return the ordered variant names this pipeline should OCR."""

    def _best_ocr_text(self, receipt: Receipt) -> tuple[str, Optional[str]]:
        """OCR selected variants, keep the longest text and its method."""
        variants: Dict[str, np.ndarray] = receipt.processed_images or {}
        best_text, best_method = "", None

        for method in self._select_variants(receipt):
            if method not in variants:
                continue
            text = self.ocr.extract_text(variants[method]).strip()
            logger.debug(f"[{self.name}] variant '{method}': {len(text)} chars")
            if len(text) > len(best_text):
                best_text, best_method = text, method
            if self._good_enough(best_text):
                break
        return best_text, best_method

    def _good_enough(self, text: str) -> bool:
        """Early-stop heuristic; overridable per pipeline."""
        return len(text) > 200

    def process_receipt(self, receipt: Receipt) -> Receipt:
        """Template method: OCR -> field extraction -> populate Receipt."""
        self.last_ocr_text = None
        if not getattr(receipt, "processed_images", None):
            logger.warning(f"[{self.name}] receipt has no processed images")
            receipt.confidence = 0
            receipt.extracted_text = ""
            receipt.selected_method = None
            return receipt

        text, method = self._best_ocr_text(receipt)
        self.last_ocr_text = text
        if not text:
            logger.warning(f"[{self.name}] OCR produced no text")
            receipt.confidence = 0
            receipt.extracted_text = ""
            receipt.selected_method = method
            return receipt

        fields = self.fields.extract(text)

        receipt.vendor = fields.vendor
        receipt.amount = fields.amount
        receipt.date = fields.date
        receipt.extracted_text = text
        receipt.selected_method = method
        receipt.confidence = fields.confidence

        logger.info(
            f"[{self.name}] vendor={fields.vendor}, amount={fields.amount}, "
            f"date={fields.date.date() if fields.date else None}, "
            f"confidence={fields.confidence}, method={method}"
        )
        return receipt