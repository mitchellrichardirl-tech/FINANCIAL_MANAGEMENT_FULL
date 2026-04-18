"""
Transaction categorization pipeline: the entry point for party assignment.

Orchestrates `PartyExtractor` and `PartyMatcher` into a single `categorize()`
call. Callers (primarily `StatementProcessor`) pass a list of raw description
strings and get back party_id + confidence per row — they don't need to know
about cleaning, extraction, or fuzzy matching.

For offline use or testing, pass `use_db=False` to swap in `PartyMatcherRaw`
which runs the same algorithm without touching the database.
"""

from typing import Dict, List, Union

import pandas as pd

from src.categorizer.party_extractor import PartyExtractor
from src.categorizer import get_party_matcher
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TransactionCategorizer:
    """
    Orchestrates the full description → party pipeline.

    Composes:
      - `PartyExtractor` — strips noise, extracts a stable party name
      - `PartyMatcher` (or `PartyMatcherRaw`) — fuzzy-matches that name
        against known parties, creating new ones when needed

    This is the class `StatementProcessor` injects and the only categorizer
    interface statement parsers should depend on. The extractor/matcher split
    is an implementation detail.

    Args:
        similarity_threshold: Passed through to the matcher. Minimum
            rapidfuzz score to accept a fuzzy match (0–100). Default 80
            (stricter than `PartyMatcher`'s default of 70 — at statement
            scale, false positives are more costly than missed matches).
        use_db: If False, uses `PartyMatcherRaw` — same algorithm but no
            DB reads or writes. Useful for tests and offline scripts.
    """

    def __init__(self, similarity_threshold: int = 80, use_db: bool = True):
        self.extractor = PartyExtractor()
        self.matcher = get_party_matcher(
            similarity_threshold=similarity_threshold,
            use_db=use_db
            )
        logger.info(
            f"Initialized TransactionCategorizer: threshold={similarity_threshold}"
        )

    def categorize(
        self, transactions: List[str]
    ) -> List[Dict[str, Union[int, None]]]:
        """
        Run the full pipeline on a list of raw transaction descriptions.

        Pipeline:
            1. Vectorised clean — strip prefixes, dates, ref numbers (PartyExtractor)
            2. Vectorised extraction — remove stop words, take first N words
            3. Batch match — deduplicated fuzzy match → party_id + confidence
            (see PartyMatcher.find_matches_batch for the optimisation detail)

        Empty or whitespace-only descriptions short-circuit to party name
        "UNKNOWN" before reaching the matcher.

        Args:
            transactions: Raw description strings, one per transaction.
                Order is preserved in the output.

        Returns:
            List of dicts, one per input, each with:
            - `cleaned_description` — normalised party name string
            - `party_id`            — matched or newly created party id,
                                        None for UNKNOWN descriptions
            - `confidence`          — 0–100 match score

        Raises:
            ValueError: If `transactions` is empty.

        Side effects:
            Resets matcher counters at the start of each call, so per-batch
            stats (`new_parties`, `new_aliases`) reflect this call only.
            New parties and aliases are written to the DB (unless `use_db=False`).
        """
        if not transactions:
            raise ValueError("No transactions data provided")

        total = len(transactions)
        logger.info(f"Starting categorization of {total} transactions")
        self.matcher.reset_counts()

        # Convert to Series for vectorized ops
        desc_series = pd.Series(transactions)

        # ── Stage 1: vectorized cleaning ──
        logger.debug("Stage 1: Cleaning descriptions")
        cleaned = self.extractor.clean_batch(desc_series)

        # ── Stage 2: vectorized party extraction ──
        logger.debug("Stage 2: Extracting party names")
        # Handle empty/blank -> UNKNOWN before extraction
        empty_mask = cleaned.str.strip() == ''
        unknown_count = empty_mask.sum()
        party_names = self.extractor.extract_party_names_batch(cleaned)
        party_names = party_names.where(~empty_mask, 'UNKNOWN')

        # ── Stage 3: batch matching ──
        logger.debug("Stage 3: Matching parties")
        result_df = self.matcher.find_matches_batch(party_names)

        new_aliases, new_parties = self.matcher.get_new_counts()

        logger.info(
            f"Categorization complete: {total} transactions mapped | "
            f"new_parties={new_parties}, new_aliases={new_aliases}, "
            f"unknown_descriptions={unknown_count}"
        )

        return result_df.to_dict('records')