from typing import Dict, List, Union

import pandas as pd

from src.categorizer.party_extractor import PartyExtractor
from src.categorizer.party_matcher import PartyMatcher
from src.categorizer.party_matcher_raw import PartyMatcherRaw
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TransactionCategorizer:
    """Main categorizer that orchestrates the categorization pipeline."""

    def __init__(self, similarity_threshold: int = 80, use_db: bool = True):
        self.extractor = PartyExtractor()
        if use_db:
            self.matcher = PartyMatcher(similarity_threshold=similarity_threshold)
        else:
            self.matcher = PartyMatcherRaw(similarity_threshold=similarity_threshold)

        logger.info(
            f"Initialized TransactionCategorizer: threshold={similarity_threshold}"
        )

    def categorize(
        self, transactions: List[str]
    ) -> List[Dict[str, Union[int, None]]]:
        """
        Categorize a list of transaction descriptions.
        
        Pipeline:
            1. Vectorized clean (pd.Series.str operations)
            2. Vectorized party name extraction
            3. Batch matching (deduplicated fuzzy matching)
        
        Returns:
            List of dicts with cleaned_description, party_id, confidence
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