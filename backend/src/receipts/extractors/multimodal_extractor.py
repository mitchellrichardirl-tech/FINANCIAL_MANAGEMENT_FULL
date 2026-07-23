from src.receipts.base import ReceiptExtractorBase
from src.receipts.engines.multimodal_engine import MultimodalEngine
from src.receipts.field_extractors.gemini_extractor import MultiModalFieldExtractor, GeminiFieldExtractor
from src.models.receipt import Receipt

class MultimodalExtractor(ReceiptExtractorBase):
    """Multimodal LLM"""

    def __init__(self,
                 ocr: MultimodalEngine,
                 fields: MultiModalFieldExtractor):
        super().__init__(
            ocr,
            fields
            )

    def _select_variants(self, receipt: Receipt) -> list[str]:
        raise NotImplementedError('_select_variants not implemented for Multimodal Extractor')
      
    def _best_ocr_text(self, receipt: Receipt) -> tuple[str, str | None]:
        img_byte_str = self.ocr.extract_text(image=receipt.original_image)
        return img_byte_str, "Conversion to byte string for communication with Multimodal Model"

    async def aprocess_receipt(self, receipt: Receipt) -> Receipt:
        """Async template method: OCR -> field extraction -> populate Receipt."""
        prepared = self._prepare(receipt)
        if prepared is None:
            return receipt
        text, method = prepared
        fields = await self.fields.aextract(text)
        return self._populate(receipt, fields, text, method)
    
if __name__ == "__main__":
    print('Setting up extractor')
    extractor = MultimodalExtractor(MultimodalEngine(), GeminiFieldExtractor())
    print('Extractor created')
    from src.receipts.receipt_loader import ReceiptLoader
    loader = ReceiptLoader()
    print('Loader created')
    receipt = list(loader.process_file("/workspaces/FINANCIAL_MANAGEMENT_FULL/data/uploads/receipt_20260618_192213_20240203_174427565_iOS_398a2097.png"))[0]
    print('Receipt loaded')
    import asyncio
    print(asyncio.run(extractor.aprocess_receipt(receipt)))