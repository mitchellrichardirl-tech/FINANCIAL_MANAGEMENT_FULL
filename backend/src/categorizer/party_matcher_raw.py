from typing import Dict, Optional, Tuple

from src.categorizer.party_matcher import PartyMatcher
from src.database.repositories.categories import CategoryRepository

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)

class PartyMatcherRaw(PartyMatcher):
    """A version of PartyMatcher that does not use the database for matching.
    
    This is useful for testing the fuzzy matching logic in isolation, without
    side effects from database interactions. It will still use the DB to load
    known parties if `use_db=True`, but it will not add new parties or aliases.
    """

    def __init__(
        self,
        similarity_threshold: int = 70
    ):
        super().__init__(db=None, similarity_threshold=similarity_threshold)

    def _intialize_database(self, db: Optional[CategoryRepository] = None):
        # Override to skip DB initialization
        return
    
    def _load_known_parties(self) -> Dict[str, int]:
        logger.debug("Initializing empty party mapping (no DB)")
        self.alias_mapping = {}

        # Pre-build the list once; we'll refresh it when aliases are added
        self._alias_keys = []

        total_unique = 0

        logger.info(
            f"Loaded {total_unique} unique parties "
            f"with {len(self.alias_mapping)} total aliases"
        )

        return self.alias_mapping
    
    def _add_unknown_party(self, party_name: str) -> int:
        self.alias_mapping[party_name] = max(list(self.alias_mapping.values()), default=0) + 1
        self._alias_keys.append(party_name)
        return self.alias_mapping[party_name]
    
    def _prime_unknown_type_cache(self):
        return