"""LLM field extractor via the LLM Gateway, with optional regex backfill."""
import os
from datetime import datetime
from typing import Optional
import requests
from src.receipts.base import FieldExtractor, ExtractedFields
from src.receipts.field_extractors.regex_extractor import RegexFieldExtractor
from src.utils.logging import ContextLogger
logger = ContextLogger(__name__)
PROMPT = """You extract structured data from OCR'd receipt text.
The text may contain OCR errors, broken lines, and noise.
Extract exactly:
- "vendor": the merchant/store name (string, or null)
- "date": the purchase date in YYYY-MM-DD format (string, or null)
- "amount": the FINAL total paid as a number (float, or null)
Rules:
- "amount" is the grand total the customer paid, not subtotal or tax.
- If the date is ambiguous, prefer day-first (European) interpretation.
- Do not invent values. Use null when unsure.
Receipt text:
\"\"\"
{ocr_text}
\"\"\"
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
class LLMFieldExtractor(FieldExtractor):
    """LLM extraction via the gateway, with an optional regex safety net."""
    # TODO: move fallback orchestration out of the extractor entirely.
    #       enable_fallback is an interim seam toward that.
    def __init__(
        self,
        base_url: str = "http://llm_gateway-api-1:8000",
        model: str = "llama3.2",
        api_key: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 120.0,
        temperature: Optional[float] = None,
        enable_fallback: bool = True,
        fallback: Optional[RegexFieldExtractor] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key if api_key is not None else os.environ.get("LLM_GATEWAY_API_KEY")
        self.max_retries = max_retries
        self.timeout = timeout
        self.temperature = temperature
        self.enable_fallback = enable_fallback
        self.fallback = fallback or RegexFieldExtractor()
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key
        # Surfaced so the harness can assert the LLM actually ran (not silently all-backfill).
        self.llm_calls = 0
        self.llm_failures = 0
    
    @property
    def name(self) -> str:
        return "llm"
    
    def extract(self, text: str) -> ExtractedFields:
        if not text.strip():
            return ExtractedFields()
        llm = self._run_llm(text)
        if not self.enable_fallback:
            return llm
        fb = self.fallback.extract(text)  # cheap; used only to backfill
        return ExtractedFields(
            vendor=llm.vendor or fb.vendor,
            amount=llm.amount if llm.amount is not None else fb.amount,
            date=llm.date or fb.date,
        )
    
    def _run_llm(self, text: str) -> ExtractedFields:
        self.llm_calls += 1
        payload = {
            "prompt": PROMPT.format(ocr_text=text[:6000]),
            "schema": RECEIPT_SCHEMA,
            "model": self.model,
            "max_retries": self.max_retries,
        }
        # Only send temperature if explicitly set. If the gateway's request model
        # forbids extra fields, an unknown key returns a *request-validation* 422 —
        # indistinguishable by status code from a model-output 422 below. Confirm the
        # endpoint accepts it before relying on it (see caveats).
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        try:
            resp = self.session.post(
                f"{self.base_url}/generate-structured",
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error(f"[llm] gateway unreachable: {e}")
            self.llm_failures += 1
            return ExtractedFields()
        if resp.status_code == 200:
            try:
                data = resp.json().get("data") or {}
                return self._normalise(data)
            except (ValueError, KeyError) as e:
                logger.error(f"[llm] malformed 200 response: {e}")
                self.llm_failures += 1
                return ExtractedFields()
        self.llm_failures += 1
        if resp.status_code == 422:
            # Model couldn't produce schema-valid JSON after retries. Per-receipt, expected sometimes.
            logger.warning("[llm] schema-invalid after retries (422) for this receipt")
        elif resp.status_code == 502:
            # Ollama itself down/erroring — infra-level, likely affects the whole run.
            logger.error(f"[llm] gateway reports Ollama error (502): {resp.text[:200]}")
        else:
            logger.error(f"[llm] unexpected status {resp.status_code}: {resp.text[:200]}")
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