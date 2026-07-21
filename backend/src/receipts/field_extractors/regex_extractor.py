"""Regex/heuristic field extractor (original parsing logic)."""

import re
from datetime import datetime
from typing import Optional

from src.receipts.base import FieldExtractor, ExtractedFields
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class RegexFieldExtractor(FieldExtractor):
    """Original heuristics: pattern lists for vendor/amount/date."""

    MIN_AMOUNT, MAX_AMOUNT, MIN_YEAR = 0.01, 10000, 2000
    MAX_VENDOR_LEN, MIN_VENDOR_LEN = 50, 3
    VENDOR_SEARCH_LINES, VENDOR_HEURISTIC_LINES = 10, 5

    def __init__(self):
        self.vendor_patterns = [
            r"(euro\s*giant|eurogiant)",
            r"(walmart|target|costco|kroger|safeway|cvs|walgreens)",
            r"(tesco|asda|sainsbury|morrisons|aldi|lidl)",
            r"([A-Z][A-Za-z\s&\-\.]{3,30}(?:store|shop|market|retail)?)",
        ]
        self.amount_patterns = [
            r"(?:total|amount\s+due|balance|grand\s+total)[\s:€$£]*(\d+[.,]\d{2})",
            r"(?:total)[\s:]*[€$£]?\s*(\d+[.,]\d{2})",
            r"[€$£]\s*(\d+[.,]\d{2})",
            r"(\d+[.,]\d{2})\s*(?:EUR|USD|GBP|€|$|£)",
        ]
        self.date_patterns = [
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}",
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}",
        ]

    @property
    def name(self) -> str:
        return "regex"

    def _clean(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.replace("|", "I").replace("!", "i")

    def _vendor(self, text: str) -> Optional[str]:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        cleaned = [self._clean(l) for l in lines]
        for pat in self.vendor_patterns:
            for line in cleaned[:self.VENDOR_SEARCH_LINES]:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
        for line in lines[:self.VENDOR_HEURISTIC_LINES]:
            if self.MIN_VENDOR_LEN < len(line) < self.MAX_VENDOR_LEN:
                words = line.split()
                if words and words[0][0].isupper():
                    return line
        return None

    def _amount(self, text: str) -> Optional[float]:
        amounts = []
        for pat in self.amount_patterns:
            for m in re.findall(pat, text, re.IGNORECASE | re.MULTILINE):
                try:
                    v = float(m.replace("€", "").replace("$", "")
                              .replace("£", "").replace(",", ".").strip())
                    if self.MIN_AMOUNT <= v <= self.MAX_AMOUNT:
                        amounts.append(v)
                except ValueError:
                    continue
        return max(amounts) if amounts else None

    def _date(self, text: str) -> Optional[datetime]:
        fmts = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
                "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y",
                "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"]
        for pat in self.date_patterns:
            for m in re.findall(pat, text, re.IGNORECASE | re.MULTILINE):
                for fmt in fmts:
                    try:
                        d = datetime.strptime(m.strip(), fmt)
                        if self.MIN_YEAR <= d.year <= datetime.now().year + 1:
                            return d
                    except ValueError:
                        continue
        return None

    def extract(self, text: str) -> ExtractedFields:
        return ExtractedFields(
            vendor=self._vendor(text),
            amount=self._amount(text),
            date=self._date(text),
        )