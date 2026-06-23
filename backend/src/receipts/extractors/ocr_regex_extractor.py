"""Legacy pipeline: Tesseract OCR + regex parsing."""

from typing import Optional

from src.receipts.base import ReceiptExtractorBase
from src.receipts.engines.tesseract_engine import TesseractEngine
from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.models.receipt import Receipt


class OCRRegexExtractor(ReceiptExtractorBase):
    """Reproduces the original 'try every variant' Tesseract behaviour."""

    def __init__(self, tesseract_path: Optional[str] = None):
        super().__init__(TesseractEngine(tesseract_path), RegexFieldExtractor())

    def _select_variants(self, receipt: Receipt) -> list[str]:
        # Original tried *all* variants.
        return list((receipt.processed_images or {}).keys())

    def _good_enough(self, text: str) -> bool:
        # Original never early-stopped on text length (it used confidence==3,
        # which the template doesn't model); keep trying all variants.
        return False