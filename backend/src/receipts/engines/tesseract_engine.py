"""Tesseract OCR engine (wraps the original multi-PSM logic)."""

from typing import Optional
import numpy as np
import pytesseract

from src.receipts.base import OCREngine
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TesseractEngine(OCREngine):
    """Original engine: tries multiple PSM modes, keeps the longest text."""

    OCR_TIMEOUT = 20
    CONFIGS = ["--psm 6 --oem 1", "--psm 4 --oem 1", "--psm 3 --oem 1"]

    def __init__(self, tesseract_path: Optional[str] = None):
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    @property
    def name(self) -> str:
        return "tesseract"

    def extract_text(self, image: np.ndarray) -> str:
        if image is None or image.size == 0:
            return ""
        best, best_len = "", 0
        for config in self.CONFIGS:
            try:
                text = pytesseract.image_to_string(
                    image, config=config, timeout=self.OCR_TIMEOUT
                )
                if len(text) > best_len:
                    best, best_len = text, len(text)
            except Exception as e:
                logger.warning(f"Tesseract config '{config}' failed: {e}")
        return best