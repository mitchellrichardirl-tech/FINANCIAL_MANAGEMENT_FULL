import re
from typing import List, Set, Optional

import pandas as pd

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PartyExtractor:
    """Handles cleaning and normalization of transaction descriptions."""

    DEFAULT_PATTERNS = [
        r'^(PAYMENT TO|TRANSFER TO|TRANSFER FROM|PURCHASE AT|POS TRANSACTION|'
        r'ONLINE PAYMENT|DIRECT DEBIT|DIRECT CREDIT|DEBIT CARD|CREDIT CARD)\s+',
        r'^(POS|CNC|TKN|DD|CT|VPP|INET|Rtd)\s+',
        r'^(PAYMENT|TRANSFER|PURCHASE|DEBIT|CREDIT)\s+',
        r'\s+\d{2}/\d{2}/\d{2,4}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}:\d{2}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}$',
        r'\s+\d{4,}$',
        r'\s+REF:.*$',
        r'\s+\*{4}\d{4}$',
        r'\s+\d{2}-\d{2}-\d{2,4}.*$',
        r'\s+\d{1,2}:\d{2}.*$',
        r'\s+\d{1,3}$',
        r'\s+[A-Z]\d{1,3}$',
        r'\s+#\d+.*$',
    ]

    DEFAULT_STOP_WORDS = {
        'THE', 'AND', 'OR', 'FOR', 'WITH', 'AT', 'IN', 'ON', 'TO', 'FROM',
        'PAYMENT', 'TRANSFER', 'TRANSACTION', 'PURCHASE', 'DEBIT', 'CREDIT',
        'ONLINE', 'DIRECT', 'WITHDRAWAL', 'DEPOSIT', 'FOREIGN',
        'CARD', 'VISA', 'MASTERCARD', 'AMEX', 'AMERICAN', 'EXPRESS',
        'POS', 'ATM', 'CNC', 'TKN', 'DD', 'CT', 'VPP', 'INET', 'RTD',
        'STORE', 'STORES', 'SHOP', 'CASH', 'FEE', 'FEES', 'CHARGE', 'CHARGES',
        'INTEREST', 'BRANCH', 'LOCATION', 'MERCHANT', 'SERVICE', 'SERVICES',
        'LTD', 'LIMITED', 'LLC', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION',
        'PTY', 'COMPANY', 'CO', 'GROUP', 'HOLDINGS',
        'IRELAND', 'IRISH', 'DUBLIN', 'IE', 'IRL', 'UK', 'GB', 'USA', 'US',
        'AUSTRALIA', 'AUS', 'AU',
        'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
        'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY',
        'SATURDAY', 'SUNDAY',
    }

    def __init__(
        self,
        custom_patterns: Optional[List[str]] = None,
        custom_stop_words: Optional[Set[str]] = None
    ):
        self.patterns = self.DEFAULT_PATTERNS + (custom_patterns or [])
        self.stop_words = self.DEFAULT_STOP_WORDS.union(custom_stop_words or set())

        # Pre-compile patterns once — avoids recompiling per row
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.patterns
        ]
        # Build single stop-word regex for vectorized removal
        escaped = [re.escape(w) for w in sorted(self.stop_words, key=len, reverse=True)]
        self._stop_word_pattern = re.compile(
            r'\b(' + '|'.join(escaped) + r')\b',
            re.IGNORECASE
        )

        logger.debug(
            f"Initialized PartyExtractor: "
            f"{len(self.patterns)} patterns, {len(self.stop_words)} stop words"
        )

    # ── keep the scalar methods for any non-batch callers ──

    def clean(self, description: str) -> str:
        if pd.isna(description):
            return ""
        text = str(description).upper()
        for pattern in self._compiled_patterns:
            text = pattern.sub('', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+[A-Z]\s+', ' ', text)
        return ' '.join(text.split())

    def extract_party_name(self, description: str, max_words: int = 3) -> str:
        if not description:
            return "UNKNOWN"
        words = description.split()
        meaningful = [w for w in words if w not in self.stop_words and len(w) > 1]
        if meaningful:
            return ' '.join(meaningful[:max_words]).strip()
        return description[:30] if len(description) > 30 else description

    # ── new vectorized batch methods ──

    def clean_batch(self, descriptions: pd.Series) -> pd.Series:
        """
        Vectorized cleaning of an entire Series of descriptions.
        
        Uses pd.Series.str methods instead of Python-level loops.
        """
        logger.debug(f"Batch cleaning {len(descriptions)} descriptions")

        s = descriptions.fillna('').astype(str).str.upper()

        # Apply each compiled pattern across the whole series
        for pattern in self._compiled_patterns:
            s = s.str.replace(pattern, '', regex=True)

        # Remove special characters
        s = s.str.replace(r'[^\w\s]', ' ', regex=True)

        # Remove standalone single letters
        s = s.str.replace(r'\s+[A-Z]\s+', ' ', regex=True)

        # Normalize whitespace
        s = s.str.strip().str.replace(r'\s+', ' ', regex=True)

        return s

    def extract_party_names_batch(
        self, descriptions: pd.Series, max_words: int = 3
    ) -> pd.Series:
        """
        Vectorized party name extraction from cleaned descriptions.
        
        Removes all stop words in one pass, then takes first N words.
        """
        logger.debug(f"Batch extracting party names from {len(descriptions)} descriptions")

        # Remove stop words in one vectorized regex pass
        filtered = descriptions.str.replace(
            self._stop_word_pattern, '', regex=True
        )
        # Remove any resulting short (single-char) words
        filtered = filtered.str.replace(r'\b\w\b', '', regex=True)
        filtered = filtered.str.strip().str.replace(r'\s+', ' ', regex=True)

        # Take first max_words words
        # Split, slice, rejoin — this is the one part that's hard to avoid
        extracted = filtered.apply(
            lambda x: ' '.join(x.split()[:max_words]) if x else ''
        )

        # Fill empties: fall back to truncated original, then UNKNOWN
        fallback = descriptions.str[:30]
        empty_mask = extracted.str.strip() == ''
        extracted = extracted.where(~empty_mask, fallback)
        extracted = extracted.where(extracted.str.strip() != '', 'UNKNOWN')

        return extracted