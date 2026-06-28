"""New pipeline: PaddleOCR + local LLM (regex backfill inside LLM extractor)."""

from typing import Optional

from src.receipts.base import ReceiptExtractorBase
from src.receipts.engines.multimodal_engine import MultimodalEngine
from src.receipts.field_extractors.gemini_extractor import GeminiFieldExtractor
from src.models.receipt import Receipt

class MultimodalExtractor(ReceiptExtractorBase):
    """Multimodal LLM"""

    def __init__(self,
                 ocr: Optional[MultimodalEngine]=None,
                 fields: Optional[GeminiFieldExtractor]=None):
        super().__init__(
            ocr or MultimodalEngine(),
            fields or GeminiFieldExtractor())

    def _select_variants(self, receipt: Receipt) -> list[str]:
        raise NotImplementedError('_select_variants not implemented for Multimodal Extractor')
      
    def _best_ocr_text(self, receipt: Receipt) -> tuple[str, str | None]:
        img_byte_str = self.ocr.extract_text(image=receipt.original_image)
        return img_byte_str, "Conversion to byte string for communication with Multimodal Model"
    
if __name__ == "__main__":
    extractor = MultimodalExtractor()
    from src.receipts.receipt_loader import ReceiptLoader
    loader = ReceiptLoader()
    receipt = list(loader.process_file("/workspaces/FINANCIAL_MANAGEMENT_FULL/data/uploads/receipt_20260618_192213_20240203_174427565_iOS_398a2097.png"))[0]
    print('Receipt loaded')
    print(extractor.process_receipt(receipt).confidence)