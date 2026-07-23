"""LLM field extractor via an external multimodal LLM."""

import os

from datetime import datetime
from typing import Optional

import json
import asyncio
from flask import current_app

from google.genai import errors as genai_errors

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
Receipt image follows

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

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

class SchemaParseError(ValueError):
    """Model output could not be parsed into the receipt schema.
    Deterministic at temperature=0 -- retrying costs money and
    returns the same failure.
    """

class MultiModalFieldExtractor(FieldExtractor):
    def __init__(
            self,
            model: str,
            api_key: str,
            max_retries: int = 2,
            timeout: float = 120.0,
    ):
        self.model = model
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.llm_calls = 0
        self.llm_failures = 0

    def _get_client(self):
        raise NotImplementedError('MultiModalFieldExtractor is a base class without implemented functionality')

    def extract(self, image: bytes) -> ExtractedFields:
        raise NotImplementedError('MultiModalFieldExtractor is a base class without implemented functionality')
            
class GeminiFieldExtractor(MultiModalFieldExtractor):
    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 120.0,
    ):
        super().__init__(
            model if model else current_app.config.get("GEMINI_MODEL"),
            api_key if api_key else os.environ.get("GEMINI_API_KEY"),
            max_retries,
            timeout
        )
        self.client = genai.Client(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self):
        if self.client is None:
            self.client = genai.Client(api_key=self.api_key)
        return self.client

    def _parse_response(self, response_text) -> ExtractedFields:
        if not response_text:
            raise SchemaParseError("Model returned empty output")
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text.strup("`").removeprefix("json").strip()
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError as e:
            # Response could contain private financial details. Do not expose
            # through logs above debug level
            logger.debug(
                f'Unable to convert {response_text[:200]!r} to json: {e}'
                )
            raise SchemaParseError('Unable to convert response to json') from e
        if not isinstance(response_json, dict):
            raise SchemaParseError(
                f"Expected JSON object, got {type(response_json).__name__}"
                )
        raw_date = response_json.get("date")
        parsed_date = None
        if raw_date:
            try:
                parsed_date = datetime.strptime(raw_date, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Model returned unparseable date: {raw_date!r}")
        return ExtractedFields(
            vendor=response_json.get("vendor"),
            date=parsed_date,
            amount=response_json.get("amount"),
        )

    def extract(self, image: bytes) -> ExtractedFields:
        client = self._get_client()
        response = client.interactions.create(
            model=self.model,
            input=[
                {"type": "text", "text": PROMPT},
                {"type": "image", "data": image, "mime_type": "image/png"},
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": RECEIPT_SCHEMA
            }
        )
        return self._parse_response(response.output_text)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        if isinstance(exc, genai_errors.APIError):
            return exc.code in _RETRYABLE_STATUS
        # network-level timeouts/disconnects from the underlying HTTP client
        if isinstance(exc, (asyncio.TimeoutError, ConnectionError)):
            return True
        return False

    async def aextract(self, image: bytes) -> ExtractedFields:
        client = self._get_client()
        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                self.llm_calls += 1
                response = await client.aio.interactions.create(
                    model=self.model,
                    input=[
                        {"type": "text", "text": PROMPT},
                        {"type": "image", "data": image, "mime_type": "image/jpeg"},
                    ],
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": RECEIPT_SCHEMA,
                    },
                )
                return self._parse_response(response.output_text)
            except SchemaParseError:
                self.llm_failures += 1
                raise
            except Exception as e:
                if not self._is_retryable(e):
                    self.llm_failures += 1
                    raise
                last_exc = e
                logger.warning(
                    f"Transient API error (attempt {attempt + 1})/"
                    f"{self.max_retries + 1}): {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, ...
        self.llm_failures += 1
        raise last_exc

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
    asyncio.run(extractor.aextract(image=img_byte_string))
