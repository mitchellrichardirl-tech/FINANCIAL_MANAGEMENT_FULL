"""PaddleOCR engine with layout-aware line reconstruction."""
import io
import base64
import numpy as np
from PIL import Image

from src.receipts.base import OCREngine
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class MultimodalEngine(OCREngine):
    """
    Just converts image to bytes, suitable for presenting to multimodal model.
    Sticking with misleading method names fort he time being to maintain
    backwards compatibility
    """

    def __init__(self, lang: str = "en"):
        self.lang = lang

    @property
    def name(self) -> str:
        return "multimodal"

    def extract_text(self, image: np.ndarray) -> str:
        if image is None or image.size == 0:
            raise ValueError('You must provide an image to convert to a byte string')
        if image.dtype != np.uint8:
            if np.issubdtype(image.dtype, np.floating):
                image = np.clip(image, 0.0, 1.0)
                image = (image * 255).astype(np.uint8)
            else:
                image = image.astype(np.uint8)
        try:
            img_pil = Image.fromarray(image, 'RGB')
            buffer = io.BytesIO()
            img_pil.save(buffer, format='PNG')
            img_bytes = buffer.getvalue()
            return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Unable to convert image to bytes: {e}")
            raise