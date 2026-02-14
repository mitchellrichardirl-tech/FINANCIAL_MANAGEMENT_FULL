from typing import Dict, List, Union

from src.categorizer.party_extractor import PartyExtractor
from src.categorizer.party_matcher import PartyMatcher
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TransactionCategorizer:
    """Main categorizer class that orchestrates the categorization process."""

    def __init__(self, similarity_threshold: int = 80):
        self.extractor = PartyExtractor()
        self.matcher = PartyMatcher(similarity_threshold=similarity_threshold)

        logger.info(f"Initialized TransactionCategorizer: threshold={similarity_threshold}")

    def categorize(
        self, transactions: List[str]
    ) -> List[Dict[str, Union[int, None]]]:
        """
        Categorize a list of transaction descriptions.
        
        Args:
            transactions: List of raw transaction description strings
            
        Returns:
            List of dicts with cleaned_description, party_id, and confidence
        """
        if not transactions:
            raise ValueError("No transactions data provided")

        total = len(transactions)
        logger.info(f"Starting categorization of {total} transactions")

        party_mapping_ids = []
        self.matcher.reset_counts()
        unknown_count = 0

        for idx, description in enumerate(transactions):
            if (idx + 1) % 500 == 0:
                logger.debug(f"Processing transaction {idx + 1}/{total}")

            if not description or description.strip() == '':
                extracted = 'UNKNOWN'
                unknown_count += 1
            else:
                cleaned = self.extractor.clean(description)
                extracted = self.extractor.extract_party_name(cleaned)

            party_id, confidence = self.matcher.find_match(extracted)

            party_mapping_ids.append({
                'cleaned_description': extracted,
                'party_id': party_id,
                'confidence': confidence
            })

        new_aliases, new_parties = self.matcher.get_new_counts()

        logger.info(
            f"Categorization complete: {total} transactions mapped | "
            f"new_parties={new_parties}, new_aliases={new_aliases}, "
            f"unknown_descriptions={unknown_count}"
        )

        return party_mapping_ids
