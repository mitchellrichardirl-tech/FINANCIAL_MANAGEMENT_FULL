from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from rapidfuzz import fuzz, process
USING_RAPIDFUZZ = True

from src.database.repositories.categories import CategoryRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PartyMatcher:
    """Handles party identification and fuzzy matching."""

    def __init__(
        self,
        db: Optional[CategoryRepository] = None,
        similarity_threshold: int = 70,
        use_db: bool = True
    ):
        if not 0 <= similarity_threshold <= 100:
            raise ValueError(
                f"Similarity threshold must be between 0 and 100. "
                f"{similarity_threshold} provided"
            )

        self.similarity_threshold = similarity_threshold
        if use_db:
            self.db = db if db else CategoryRepository()
        self.last_match_score: int = 0
        self.new_aliases = 0
        self.new_parties = 0
        self._load_known_parties()
        self.log_freq = 10  # Log every N fuzzy matches

        logger.debug(
            f"Initialized PartyMatcher: threshold={similarity_threshold}, "
            f"using={'rapidfuzz' if USING_RAPIDFUZZ else 'fuzzywuzzy'}"
        )

    def _intermittent_log(self, idx: int, total: int, message: str = ""):
        if (idx + 1) % self.log_freq == 0 or idx == total - 1:
            logger.debug(f"{message} {idx + 1}/{total}")

    def _load_known_parties(self) -> Dict[str, int]:
        logger.debug("Loading known parties from database")
        self.alias_mapping = self.db.get_all_party_aliases()

        # Pre-build the list once; we'll refresh it when aliases are added
        self._alias_keys = list(self.alias_mapping.keys())

        total_unique = len(set(self.alias_mapping.values()))
        logger.info(
            f"Loaded {total_unique} unique parties "
            f"with {len(self.alias_mapping)} total aliases"
        )
        return self.alias_mapping

    def _refresh_alias_keys(self):
        """Rebuild the alias key list after mutations."""
        self._alias_keys = list(self.alias_mapping.keys())

    @staticmethod
    def custom_scorer(s1, s2, score_cutoff=0):
        """Custom scorer that balances character and token matching.

        Uses score_cutoff for early termination when available (rapidfuzz).
        Falls back gracefully when called without it (fuzzywuzzy).
        """
        char_score = fuzz.ratio(s1, s2)

        # If the full character score already beats the cutoff, no need
        # to compute partial_ratio at all
        if char_score >= score_cutoff:
            partial_score = fuzz.partial_ratio(s1, s2)
            return max(char_score, partial_score * 0.95)

        # char_score is below cutoff — check if partial could save it.
        # partial_ratio >= ratio in most cases, and we scale it by 0.95,
        # so the maximum possible score from the partial path is
        # partial_ratio * 0.95. Only worth computing if it could beat cutoff.
        partial_score = fuzz.partial_ratio(s1, s2)
        best = max(char_score, partial_score * 0.95)

        # Return 0 if below cutoff — this is the rapidfuzz convention
        # for signalling "not a match" during extractOne
        if best < score_cutoff:
            return 0

        return best

    # ── scalar methods (unchanged interface) ──

    def _check_exact_match(self, party_name: str) -> int:
        try:
            return self.alias_mapping[party_name]
        except KeyError:
            raise KeyError(f"No exact match found for '{party_name}'")

    def _add_unknown_party(self, party_name: str) -> int:
        return self.db.add_party_unknown_type(party_name)
    
    def _prime_unknown_type_cache(self):
        self.db.prime_unknown_type_cache()

    def _check_fuzzy_match(self, party_name: str) -> Tuple[int, int]:
        if not self.alias_mapping:
            raise LookupError(f"No known parties to match against")

        best_match = process.extractOne(
            party_name,
            self._alias_keys,
            scorer=self.custom_scorer
        )

        if best_match and best_match[1] >= self.similarity_threshold:
            matched_name, score = best_match[0], best_match[1]
            self.last_match_score = score
            party_id = self.alias_mapping[matched_name]

            if party_name not in self.alias_mapping:
                self.alias_mapping[party_name] = party_id
                self._refresh_alias_keys()
                self.new_aliases += 1
                logger.debug(
                    f"Fuzzy matched '{party_name}' -> '{matched_name}' "
                    f"(score={score}) — added as alias"
                )

            return party_id, score

        best_score = best_match[1] if best_match else 0
        raise KeyError(
            f"No match above threshold {self.similarity_threshold} "
            f"(best={best_score})"
        )

    def find_match(self, party_name: str) -> Tuple[int, int]:
        if not party_name or party_name.strip() == "":
            raise ValueError("No party name provided")
        self.last_match_score = 0

        try:
            party_id = self._check_exact_match(party_name)
            self.last_match_score = 100
            return party_id, 100
        except KeyError:
            pass

        try:
            return self._check_fuzzy_match(party_name)
        except (LookupError, KeyError):
            pass

        party_id = self._add_unknown_party(party_name)
        self.alias_mapping[party_name] = party_id
        self._refresh_alias_keys()
        self.new_parties += 1
        logger.info(f"Created new party '{party_name}' with id {party_id}")
        return party_id, 100

    # ── new batch method ──

    def find_matches_batch(self, party_names: pd.Series) -> pd.DataFrame:
        """
        Match an entire Series of extracted party names.
        
        Optimizations applied:
          1. Deduplicate — only process each unique name once
          2. Exact matches via dict lookup (vectorized with .map)
          3. Fuzzy matching only on the remaining unmatched unique names
          4. All results broadcast back to the original index
        
        Args:
            party_names: Series of extracted party name strings
            
        Returns:
            DataFrame with columns: cleaned_description, party_id, confidence
        """
        total = len(party_names)
        logger.info(f"Batch matching {total} party names")

        # ── Step 1: deduplicate ──
        unique_names = party_names.unique()
        unique_count = len(unique_names)
        logger.info(
            f"Deduplicated to {unique_count} unique names "
            f"({total - unique_count} duplicates skipped)"
        )

        # We'll build results for each unique name
        results: Dict[str, Tuple[int, int]] = {}

        # ── Step 2: exact matches (bulk dict lookup) ──
        for name in unique_names:
            if not name or name.strip() == '':
                continue
            if name in self.alias_mapping:
                results[name] = (self.alias_mapping[name], 100)

        exact_count = len(results)
        logger.info(f"Exact matches: {exact_count}/{unique_count}")

        # ── Step 3: fuzzy match only the remaining names ──
        unmatched = [
            n for n in unique_names
            if n and n.strip() != '' and n not in results
        ]

        logger.debug(f"{len(unmatched)} unique names to fuzzy match after exact matches")
        

        if unmatched:
            logger.info(
                f"Fuzzy matching {len(unmatched)} unique names "
                f"against {len(self._alias_keys)} known aliases"
            )
            self._prime_unknown_type_cache()

            if self._alias_keys:
                ratio_scores   = process.cdist(unmatched, self._alias_keys, scorer=fuzz.ratio,         workers=-1)
                partial_scores = process.cdist(unmatched, self._alias_keys, scorer=fuzz.partial_ratio, workers=-1)
                scores = np.maximum(ratio_scores, partial_scores * 0.95)
                best_idx = scores.argmax(axis=1)
                best_score = scores.max(axis=1)
            else:
                best_score = np.full(len(unmatched), -1.0)
                best_idx = None

            needs_new_party: list[str] = []

            for idx, name in enumerate(unmatched):
                if best_score[idx] >= self.similarity_threshold:
                    matched_name = self._alias_keys[best_idx[idx]]
                    party_id = self.alias_mapping[matched_name]
                    results[name] = (party_id, int(best_score[idx]))
                    if name not in self.alias_mapping:
                        self.alias_mapping[name] = party_id
                        self.new_aliases += 1
                else:
                    needs_new_party.append(name)       # defer, don't insert

            # One transaction for all new parties
            if needs_new_party:
                logger.info(f"Creating {len(needs_new_party)} new parties in one transaction")
                new_ids = self.db.bulk_add_parties_unknown_type(needs_new_party)
                for name in needs_new_party:
                    pid = new_ids.get(name)
                    if pid is not None:
                        results[name] = (pid, 100)
                        self.alias_mapping[name] = pid
                        self.new_parties += 1
                    else:
                        # Shouldn't happen, but don't leave a hole in results
                        logger.warning(f"Bulk insert returned no id for {name!r}")
                        results[name] = (None, 0)

            self._refresh_alias_keys()

        # Handle any blank/empty names that slipped through
        for name in unique_names:
            if name not in results:
                results[name] = (None, 0)

        # ── Step 4: broadcast back to original index ──
        result_df = pd.DataFrame({
            'cleaned_description': party_names,
            'party_id': party_names.map(lambda n: results.get(n, (None, 0))[0]),
            'confidence': party_names.map(lambda n: results.get(n, (None, 0))[1]),
        })

        fuzzy_count = len(results) - exact_count
        logger.info(
            f"Batch matching complete: exact={exact_count}, "
            f"fuzzy={fuzzy_count}, new_parties={self.new_parties}"
        )

        return result_df

    def reset_counts(self):
        self.new_aliases = 0
        self.new_parties = 0

    def get_new_counts(self) -> Tuple[int, int]:
        return self.new_aliases, self.new_parties
    
def get_party_matcher(similarity_threshold: int = 70, use_db: bool = True) -> PartyMatcher:
    """Factory function to get a PartyMatcher instance."""
    if use_db:
        return PartyMatcher(similarity_threshold=similarity_threshold, use_db=True)
    return PartyMatcherRaw(similarity_threshold=similarity_threshold)