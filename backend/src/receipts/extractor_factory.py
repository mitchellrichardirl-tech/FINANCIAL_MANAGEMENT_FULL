"""Factory for constructing receipt extractors inside worker processes."""
from typing import Dict, Optional

# Per-process cache: each pool worker builds its extractor once and
# reuses it (and its underlying HTTP client) across tasks.
_EXTRACTOR_CACHE: Dict[tuple, object] = {}

def create_extractor(method: str = "ocr", config: Optional[Dict] = None):
    config = config or {}
    if method == "multimodal":
        # Imports deferred so OCR-only deployments don't need google-genai
        from src.receipts.extractors.multimodal_extractor import MultimodalExtractor
        from src.receipts.engines.multimodal_engine import MultimodalEngine
        from src.receipts.field_extractors.gemini_extractor import GeminiFieldExtractor
        return MultimodalExtractor(
            ocr=MultimodalEngine(),
            fields=GeminiFieldExtractor(
                model=config.get("model", "gemini-3.5-flash"),
                # api_key deliberately NOT passed through config -- the
                # extractor falls back to GEMINI_API_KEY in the worker's
                # environment, so the key never transits pickled task args.
                max_retries=config.get("max_retries", 2),
                timeout=config.get("timeout", 120.0),
            ),
        )
    if method == "ocr":
        from src.receipts.receipt_extractor import ReceiptExtractor
        return ReceiptExtractor()
    raise ValueError(f"Unknown extraction method: {method!r}")

def get_extractor(method: str = "ocr", config: Optional[Dict] = None):
    key = (method, tuple(sorted((config or {}).items())))
    if key not in _EXTRACTOR_CACHE:
        _EXTRACTOR_CACHE[key] = create_extractor(method, config)
    return _EXTRACTOR_CACHE[key]