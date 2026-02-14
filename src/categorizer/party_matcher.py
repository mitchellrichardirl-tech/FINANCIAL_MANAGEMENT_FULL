from typing import Dict, List, Optional, Tuple

from fuzzywuzzy import fuzz, process

from src.database.repositories.categories import CategoryRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PartyMatcher:
    """Handles party identification and fuzzy matching."""

    def __init__(
        self,
        db: Optional[CategoryRepository] = None,
        similarity_threshold: int = 70
    ):
        """Initialize the matcher with similarity threshold."""
        if not 0 <= similarity_threshold <= 100:
            raise ValueError(
                f"Similarity threshold must be between 0 and 100. "
                f"{similarity_threshold} provided"
            )

        self.similarity_threshold = similarity_threshold
        self.db = db if db else CategoryRepository()
        self.last_match_score: int = 0
        self.new_aliases = 0
        self.new_parties = 0

        self._load_known_parties()

        logger.debug(
            f"Initialized PartyMatcher: threshold={similarity_threshold}"
        )

    def _load_known_parties(self) -> Dict[str, int]:
        """Load known party names and aliases from database."""
        logger.debug("Loading known parties from database")

        self.alias_mapping = self.db.get_all_party_aliases()

        total_unique = len(set(self.alias_mapping.values()))
        total_aliases = len(self.alias_mapping)

        if total_unique > 0:
            logger.info(
                f"Loaded {total_unique} unique parties "
                f"with {total_aliases} total aliases"
            )
        else:
            logger.warning("No known parties loaded from database")

        return self.alias_mapping

    def _check_exact_match(self, party_name: str) -> int:
        """Check for exact matches in alias mapping."""
        try:
            return self.alias_mapping[party_name]
        except KeyError:
            raise KeyError(f"No exact match found for '{party_name}'")

    @staticmethod
    def custom_scorer(s1, s2):
        """Custom scorer that balances character and token matching."""
        char_score = fuzz.ratio(s1, s2)
        partial_score = fuzz.partial_ratio(s1, s2)
        return max(char_score, partial_score * 0.95)

    def _check_fuzzy_match(self, party_name: str) -> Tuple[int, int]:
        """Check for fuzzy matches against all known parties."""
        if not self.alias_mapping:
            raise LookupError(
                f"No known parties to match against for '{party_name}'"
            )

        best_match = process.extractOne(
            party_name,
            list(self.alias_mapping.keys()),
            scorer=self.custom_scorer
        )

        if best_match and best_match[1] >= self.similarity_threshold:
            matched_name, score = best_match[0], best_match[1]
            self.last_match_score = score
            party_id = self.alias_mapping[matched_name]

            if party_name not in self.alias_mapping:
                self.alias_mapping[party_name] = party_id
                self.new_aliases += 1
                logger.debug(
                    f"Fuzzy matched '{party_name}' -> '{matched_name}' "
                    f"(score={score}, party_id={party_id}) — added as alias"
                )
            else:
                logger.debug(
                    f"Fuzzy matched '{party_name}' -> '{matched_name}' "
                    f"(score={score}, party_id={party_id})"
                )

            return party_id, score

        best_score = best_match[1] if best_match else 0
        raise KeyError(
            f"No match for '{party_name}' above threshold "
            f"{self.similarity_threshold} (best={best_score})"
        )

    def find_match(self, party_name: str) -> Tuple[int, int]:
        """Find the best matching party for a given name."""
        if not party_name or party_name.strip() == "":
            raise ValueError("No party name provided")

        self.last_match_score = 0

        # Try exact match first
        try:
            party_id = self._check_exact_match(party_name)
            self.last_match_score = 100
            return party_id, self.last_match_score
        except KeyError:
            pass

        # Try fuzzy match
        try:
            party_id, score = self._check_fuzzy_match(party_name)
            self.last_match_score = score
            return party_id, self.last_match_score
        except (LookupError, KeyError):
            pass

        # Create new party
        party_id = self.db.add_party_unknown_type(party_name)
        self.alias_mapping[party_name] = party_id
        self.new_parties += 1

        logger.info(f"Created new party '{party_name}' with id {party_id}")
        return party_id, 100

    def reset_counts(self):
        """Reset the counts of new aliases and parties."""
        self.new_aliases = 0
        self.new_parties = 0
        logger.debug("Match counts reset")

    def get_new_counts(self) -> Tuple[int, int]:
        """Get the counts of new aliases and parties added."""
        return self.new_aliases, self.new_parties