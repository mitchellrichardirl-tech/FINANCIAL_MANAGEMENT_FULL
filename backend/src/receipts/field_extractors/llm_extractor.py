"""LLM field extractor (Ollama) with optional regex backfill."""

import json
from datetime import datetime
from typing import Optional

import ollama

from src.receipts.base import FieldExtractor, ExtractedFields
from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)

PROMPT = """You extract structured data from OCR'd receipt text.
The text may contain OCR errors, broken lines, and noise.

Return ONLY a JSON object with exactly these keys:
- "vendor": the merchant/store name (string, or null)
- "date": the purchase date in YYYY-MM-DD format (string, or null)
- "amount": the FINAL total paid as a number (float, or null)

Rules:
- "amount" is the grand total the customer paid, not subtotal or tax.
- If the date is ambiguous, prefer day-first (European) interpretation.
- Do not invent values. Use null when unsure.
- Output nothing except the JSON object.

Receipt text:
\"\"\"
{ocr_text}
\"\"\"
"""


class LLMFieldExtractor(FieldExtractor):
    """Local-LLM extraction with regex safety net for missed fields."""
    # TODO: manage the fallback from the orchestrator, not within the extractor itself.
    def __init__(self, model: str = "qwen2.5:7b",
                 host: str = "http://localhost:11434",
                 fallback: Optional[RegexFieldExtractor] = None):
        self.model = model
        self.client = ollama.Client(host=host)
        self.fallback = fallback or RegexFieldExtractor()

    @property
    def name(self) -> str:
        return "llm"

    def extract(self, text: str) -> ExtractedFields:
        if not text.strip():
            return ExtractedFields()

        llm = self._run_llm(text)
        fb = self.fallback.extract(text)  # cheap; used only to backfill

        return ExtractedFields(
            vendor=llm.vendor or fb.vendor,
            amount=llm.amount if llm.amount is not None else fb.amount,
            date=llm.date or fb.date,
        )

    def _run_llm(self, text: str) -> ExtractedFields:
        try:
            resp = self.client.chat(
                model=self.model,
                messages=[{"role": "user",
                           "content": PROMPT.format(ocr_text=text[:6000])}],
                format="json",
                options={"temperature": 0},
            )
            data = json.loads(resp["message"]["content"])
            return self._normalise(data)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return ExtractedFields()

    def _normalise(self, data: dict) -> ExtractedFields:
        amount = data.get("amount")
        if isinstance(amount, str):
            amount = amount.replace(",", ".").replace("€", "") \
                           .replace("$", "").replace("£", "").strip()
            try:
                amount = float(amount)
            except ValueError:
                amount = None
        if amount is not None and not (0.01 <= amount <= 100000):
            amount = None

        date = self._coerce_date(data.get("date")) if data.get("date") else None
        return ExtractedFields(vendor=data.get("vendor") or None,
                               amount=amount, date=date)

    @staticmethod
    def _coerce_date(value: str) -> Optional[datetime]:
        value = value.strip()
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
                    "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None