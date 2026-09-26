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
        similarity_threshold: int = 70,
        known_aliases: Optional[dict[str, int]]=None,
        canonical_parties: Optional[dict[str, int]]=None
    ):
        self.known_aliases = dict(known_aliases) if known_aliases else {}
        self.canonical_parties = dict(canonical_parties) if canonical_parties else {}
        super().__init__(db=None, similarity_threshold=similarity_threshold)

    def _intialize_database(self, db: Optional[CategoryRepository] = None):
        # Override to skip DB initialization
        return

    def _get_raw_mapping(self) -> Dict[str, int]:
        all_aliases = dict()
        if self.known_aliases:
            all_aliases.update(self.known_aliases)
        if self.canonical_parties:
            all_aliases.update(self.canonical_parties)
        return all_aliases
    
    def _add_unknown_party(self, party_name: str) -> int:
        self.alias_mapping[party_name] = max(list(self.alias_mapping.values()), default=0) + 1
        self._alias_keys.append(party_name)
        return self.alias_mapping[party_name]
    
    def _prime_unknown_type_cache(self):
        return

    def _get_new_ids(self, needs_new_party):
        try:
            max_pid = max(self.alias_mapping.values())
        except ValueError:
            max_pid = 0
        return {new_party: max_pid + n + 1 for n, new_party in enumerate(needs_new_party)}
