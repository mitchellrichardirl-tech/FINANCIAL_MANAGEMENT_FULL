"""LLM field extractor via an external multimodal LLM."""

import os

from datetime import datetime
from typing import Optional

import json

# import requests
from src.receipts.base import ExtractedFields, FieldExtractor

# from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.utils.logging import ContextLogger

ContextLogger.setup_logging()
logger = ContextLogger(__name__)

from google import genai

PROMPT = """You extract structured data from a scanned image of a receipy.
Extract exactly:
- "vendor": the merchant/store name (string, or null)
- "date": the purchase date in YYYY-MM-DD format (string, or null)
- "amount": the FINAL total paid as a number (float, or null)
Rules:
- "amount" is the grand total the customer paid, not subtotal or tax.
- If the date is ambiguous, prefer day-first (European) interpretation.
- Do not invent values. Use null when unsure.
Receipt text:

"""
# type unions allow the model to abstain (null) rather than hallucinate;
# "required" just means the key must be present, not non-null.
RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": ["string", "null"]},
        "date":   {"type": ["string", "null"]},
        "amount": {"type": ["number", "null"]},
    },
    "required": ["vendor", "date", "amount"],
}

class GeminiFieldExtractor(FieldExtractor):
    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 120.0,
    ):
        self.model = model
        self.api_key = api_key if api_key else os.environ.get("GEMINI_API_KEY")
        self.max_retries = max_retries
        self.timeout = timeout
        self.client = genai.Client(api_key=self.api_key)
        self.llm_calls = 0
        self.llm_failures = 0

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self):
        if self.client is None:
            self.client = genai.Client(api_key=self.api_key)
        return self.client
    
    def extract(self, image: bytes) -> ExtractedFields:
        client = self._get_client()
        response = client.interactions.create(
            model=self.model,
            input=[
                {"type": "text", "text": PROMPT},
                {"type": "image", "data": image, "mime_type": "image/jpeg"},
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": RECEIPT_SCHEMA
            }
        )
        try:
            response_json = json.loads(response.output_text)
        except Exception as e:
            raise ValueError(f'Unable to convert {response.output_text[:200]} to json: {e}')
        return ExtractedFields(
            vendor=response_json.get('vendor', None),
            date=datetime.strptime(response_json.get('date'), '%Y-%m-%d') if 'date' in response_json else None,
            amount=response_json.get('amount', None)
        )


if __name__ == "__main__":
    from src.utils.image_loader import ImageLoader
    img = ImageLoader.load("/workspaces/FINANCIAL_MANAGEMENT_FULL/data/uploads/receipt_20260618_192213_20240203_174427565_iOS_398a2097.png")[0]
    logger.info("Opened receipt")
    # print(f"Type: {type(img)}")  # <class 'numpy.ndarray'>
    # print(f"Shape: {img.shape}")  # (height, width, 3) for RGB images
    # print(f"Data type: {img.dtype}")  # uint8 (0-255 integer values)
    from src.receipts.engines.multimodal_engine import MultimodalEngine
    engine = MultimodalEngine()
    logger.info("Generated multimodal engine")
    img_byte_string = engine.extract_text(img)
    logger.info("Converted image to bytes")
    # logger.info(f"Byte string is {type(img_byte_string)}")
    # import io
    # from PIL import Image
    # import base64
    # try:
    #     img_bytes = base64.b64decode(img_byte_string)
    #     img_decoded = Image.open(io.BytesIO(img_bytes))
    #     img_decoded.verify()
    #     img_decoded = Image.open(io.BytesIO(img_bytes))
    #     logger.info(f"Image is RGB? {img_decoded.mode == "RGB"}")
    # except Exception as e:
    #     logger.error(f'Not an image: {e}')
    extractor = GeminiFieldExtractor()
    logger.info("Generated gemini extractor")
    extractor.extract(image=img_byte_string)
