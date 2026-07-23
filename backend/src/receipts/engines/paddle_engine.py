"""PaddleOCR engine with layout-aware line reconstruction."""

from typing import Optional
import numpy as np

from src.receipts.base import OCREngine
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PaddleEngine(OCREngine):
    """Deep-learning OCR; reconstructs reading order from box geometry."""

    def __init__(self, lang: str = "en", use_gpu: bool = False):
        self.lang = lang
        self.use_gpu = use_gpu
        self._ocr = None

    @property
    def name(self) -> str:
        return "paddle"

    def prime(self):
        return self._engine()
            
    def _engine(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            logger.info(
                f"Initialising PaddleOCR (gpu={self.use_gpu})"
            )
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.lang,
                use_gpu=self.use_gpu
            )
        return self._ocr

    def extract_text(self, image: np.ndarray) -> str:
        if image is None or image.size == 0:
            return ""
        try:
            result = self._engine().ocr(image, cls=True)
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return ""
        if not result or not result[0]:
            return ""

        # --- line reconstruction (unchanged) ---
        items = []
        for line_data in result[0]:
            box, (text, _conf) = line_data
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append({
                "text": text, "y": sum(ys) / 4,
                "x": min(xs), "h": max(ys) - min(ys),
            })
        items.sort(key=lambda it: it["y"])

        lines, current, last_y = [], [], None
        for it in items:
            if last_y is None or abs(it["y"] - last_y) <= it["h"] * 0.6:
                current.append(it)
            else:
                lines.append(current)
                current = [it]
            last_y = it["y"]
        if current:
            lines.append(current)

        out = []
        for line in lines:
            line.sort(key=lambda it: it["x"])
            out.append(" ".join(it["text"] for it in line))
        return "\n".join(out)