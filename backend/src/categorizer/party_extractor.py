"""
Party name extraction from raw transaction descriptions.

Bank descriptions are noisy: "POS TRANSACTION TESCO METRO RATHMINES 12/03/24 REF:98765".
This module strips the noise and extracts a stable party name ("TESCO METRO RATHMINES")
that `party_matcher` can fuzzy-match against known merchants.

Two-stage pipeline, always called in order:
  1. `clean()` / `clean_batch()` — strip transaction-type prefixes, trailing
     dates, reference numbers, card masks, etc. Output is uppercase,
     whitespace-normalized.
  2. `extract_party_name()` / `extract_party_names_batch()` — drop stop words
     (LTD, DUBLIN, CARD, …) and take the first N remaining words.

Scalar methods exist for one-off use; batch methods are vectorised over
pandas Series and are what the statement import pipeline actually calls.
"""

import re
from typing import List, Set, Optional

import pandas as pd

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PartyExtractor:
    """
    Strips noise from transaction descriptions and extracts a party name.

    Two-step API — **callers must clean before extracting**:
        cleaned = extractor.clean(description)
        party   = extractor.extract_party_name(cleaned)

    Or for a whole statement:
        cleaned = extractor.clean_batch(descriptions)
        parties = extractor.extract_party_names_batch(cleaned)

    Customization: pass `custom_patterns` / `custom_stop_words` to extend
    the defaults (they're appended, not replaced). All regexes are
    pre-compiled in `__init__` so per-row cost is just the match, not
    the compile.
    """

    DEFAULT_PATTERNS = [
        # ── Leading transaction-type prefixes ──
        # Long form ("PAYMENT TO", "DIRECT DEBIT"), bank abbreviations
        # (POS, CNC, DD…), and short form ("PAYMENT", "TRANSFER").
        r'^(PAYMENT TO|TRANSFER TO|TRANSFER FROM|PURCHASE AT|POS TRANSACTION|'
        r'ONLINE PAYMENT|DIRECT DEBIT|DIRECT CREDIT|DEBIT CARD|CREDIT CARD)\s+',
        r'^(POS|CNC|TKN|DD|CT|VPP|INET|Rtd)\s+',
        r'^(PAYMENT|TRANSFER|PURCHASE|DEBIT|CREDIT)\s+',

        # ── Trailing dates / times ──
        # Various formats banks append: dd/mm/yyyy, dd/mm hh:mm, dd-mm-yyyy, hh:mm
        r'\s+\d{2}/\d{2}/\d{2,4}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}:\d{2}.*$',
        r'\s+\d{2}/\d{2}\s+\d{1,2}$',
        r'\s+\d{2}-\d{2}-\d{2,4}.*$',
        r'\s+\d{1,2}:\d{2}.*$',

        # ── Trailing reference / card / store codes ──
        # Long numbers, REF:xxx, masked cards (****1234), short codes, #123
        r'\s+\d{4,}$',
        r'\s+REF:.*$',
        r'\s+\*{4}\d{4}$',
        r'\s+\d{1,3}$',
        r'\s+[A-Z]\d{1,3}$',
        r'\s+#\d+.*$',
    ]

    DEFAULT_STOP_WORDS = {
        # Articles / conjunctions
        'THE', 'AND', 'OR', 'FOR', 'WITH', 'AT', 'IN', 'ON', 'TO', 'FROM',
        # Transaction-type words that survived pattern stripping
        'PAYMENT', 'TRANSFER', 'TRANSACTION', 'PURCHASE', 'DEBIT', 'CREDIT',
        'ONLINE', 'DIRECT', 'WITHDRAWAL', 'DEPOSIT', 'FOREIGN',
        # Card networks / channels
        'CARD', 'VISA', 'MASTERCARD', 'AMEX', 'AMERICAN', 'EXPRESS',
        'POS', 'ATM', 'CNC', 'TKN', 'DD', 'CT', 'VPP', 'INET', 'RTD',
        # Generic merchant words
        'STORE', 'STORES', 'SHOP', 'CASH', 'FEE', 'FEES', 'CHARGE', 'CHARGES',
        'INTEREST', 'BRANCH', 'LOCATION', 'MERCHANT', 'SERVICE', 'SERVICES',
        # Corporate suffixes
        'LTD', 'LIMITED', 'LLC', 'INC', 'INCORPORATED', 'CORP', 'CORPORATION',
        'PTY', 'COMPANY', 'CO', 'GROUP', 'HOLDINGS',
        # Geography (don't want "TESCO DUBLIN" and "TESCO CORK" as different parties)
        'IRELAND', 'IRISH', 'DUBLIN', 'IE', 'IRL', 'UK', 'GB', 'USA', 'US',
        'AUSTRALIA', 'AUS', 'AU',
        # Day names
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

    def clean(self, description: str) -> str:
        """
        Stage 1: strip noise from a raw description.

        Applies every pattern in sequence, then removes punctuation and
        standalone single letters, and normalizes whitespace. Output is
        uppercase.

        Returns an empty string for NaN/None input.
        """
        if pd.isna(description):
            return ""
        text = str(description).upper()
        for pattern in self._compiled_patterns:
            text = pattern.sub('', text)
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+[A-Z]\s+', ' ', text)
        return ' '.join(text.split())

    def extract_party_name(self, description: str, max_words: int = 3) -> str:
        """
        Stage 2: pull a party name from a **cleaned** description.

        Drops stop words and single-character tokens, then takes the first
        `max_words` survivors. If nothing survives, falls back to the first
        30 characters of the input. If the input itself is empty, returns
        "UNKNOWN".

        Expects output from `clean()` — feeding it a raw description will
        work but the fallback path will return raw junk.
        """
        if not description:
            return "UNKNOWN"
        words = description.split()
        meaningful = [w for w in words if w not in self.stop_words and len(w) > 1]
        if meaningful:
            return ' '.join(meaningful[:max_words]).strip()
        return description[:30] if len(description) > 30 else description

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
        Stage 2: pull a party name from a **cleaned** description.

        Drops stop words and single-character tokens, then takes the first
        `max_words` survivors. If nothing survives, falls back to the first
        30 characters of the input. If the input itself is empty, returns
        "UNKNOWN".

        Expects output from `clean()` — feeding it a raw description will
        work but the fallback path will return raw junk.
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