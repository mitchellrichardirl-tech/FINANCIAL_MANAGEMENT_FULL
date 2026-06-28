"""New pipeline: PaddleOCR + local LLM (regex backfill inside LLM extractor)."""

from typing import Optional

from src.receipts.base import ReceiptExtractorBase
from src.receipts.engines.paddle_engine import PaddleEngine
from src.receipts.field_extractors.llm_extractor import LLMFieldExtractor
from src.models.receipt import Receipt


class MultimodalExtractor(ReceiptExtractorBase):
    """PaddleOCR + LLM. Stops after the first variant that yields good text."""

    PREFERRED = ("paddle_ready", "correct_skew", "denoise")

    def __init__(self):
        super().__init__(ocr=None, fields=None)

    def _select_variants(self, receipt: Receipt) -> list[str]:
        variants = receipt.processed_images or {}
        ordered = [v for v in self.PREFERRED if v in variants]
        ordered += [v for v in variants if v not in ordered]
        return ordered