"""
Party matching: fuzzy identification of transaction counterparties.

A "party" is a normalised merchant/counterparty name (e.g. "Tesco Metro
Rathmines") derived from raw bank transaction descriptions. Matching works
in three tiers, in order:

  1. Exact   — dict lookup against known aliases (O(1))
  2. Fuzzy   — rapidfuzz similarity against all known aliases; a match
               above `similarity_threshold` is added as a new alias so
               future occurrences hit tier 1
  3. New     — no match found; a new party is created in the DB with
               type "Unknown" for the user to categorize later

Two classes:
  - `PartyMatcher`    — full DB integration (normal use)
  - `PartyMatcherRaw` — same algorithm, no DB (testing / offline use)
                        defined in `party_matcher_raw.py`

For processing a single description, use `find_match()`.
For processing a batch (e.g. an imported statement), use
`find_matches_batch()` — it deduplicates and uses vectorised scoring,
which is significantly faster at scale.
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from rapidfuzz import fuzz, process

from src.database.repositories.categories import CategoryRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class PartyMatcher:
    """
    Identifies the party for a transaction description.

    Maintains an in-memory alias map (description string → party_id) loaded
    from the DB on construction. New aliases and new parties discovered
    during a session are written back to the DB and added to the in-memory
    map so they're available immediately within the same run.

    Instance counters (`new_aliases`, `new_parties`) track what was created
    during the current session. Call `reset_counts()` between jobs if you
    need per-job stats, or `get_new_counts()` to read them.

    Args:
        db: Repository to use for party lookups and creation. Defaults to
            a fresh `CategoryRepository` if not supplied.
        similarity_threshold: Minimum rapidfuzz score (0–100) to accept a
            fuzzy match. Below this, the name becomes a new party.
            Default 70 balances recall against false positives.
    """

    def __init__(
        self,
        db: Optional[CategoryRepository] = None,
        similarity_threshold: int = 70
    ):
        if not 0 <= similarity_threshold <= 100:
            raise ValueError(
                f"Similarity threshold must be between 0 and 100. "
                f"{similarity_threshold} provided"
            )

        self.similarity_threshold = similarity_threshold
        self._intialize_database(db)
        self.last_match_score: int = 0
        self.new_aliases = 0
        self.new_parties = 0
        self._load_known_parties()
        self.log_freq = 10  # Log every N fuzzy matches

        logger.debug(
            f"Initialized PartyMatcher: threshold={similarity_threshold}"
        )

    def _intialize_database(self, db: Optional[CategoryRepository] = None):
        self.db = db if db else CategoryRepository()

    def _load_known_parties(self) -> Dict[str, int]:
        """
        Load all known party aliases from the DB into `self.alias_mapping`.

        `alias_mapping` is a flat dict of `{alias_string: party_id}`. A single
        party may have many aliases — every description that has previously
        fuzzy-matched to it becomes an alias, so future occurrences hit the
        fast exact-match path.

        Also populates `self._alias_keys` — the list form used by rapidfuzz
        `process.extractOne` and `process.cdist`.
        """
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
        """
        Scoring function passed to rapidfuzz `process` calls.

        Combines character-level and partial (substring) matching to handle
        descriptions that include store codes, locations, or card numbers
        appended to the core merchant name:

        - `fuzz.ratio`         — rewards full-string similarity
        - `fuzz.partial_ratio` — rewards the best matching substring,
                                scaled by 0.95 to slightly prefer full
                                matches when scores are otherwise equal

        The `score_cutoff` parameter is the rapidfuzz convention for early
        termination — returning 0 when the best possible score is below the
        cutoff avoids unnecessary work inside `extractOne` / `cdist`.

        Args:
            s1: Query string (extracted party name).
            s2: Candidate string (known alias).
            score_cutoff: Minimum score worth returning. Return 0 if below.

        Returns:
            Score in [0, 100], or 0 if below `score_cutoff`.
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
        """
        Identify the party for a single description string.

        Runs the three-tier lookup in order: exact → fuzzy → create new.
        Prefer `find_matches_batch()` when processing more than a handful of
        descriptions — the scalar path re-runs the full alias list for every
        fuzzy lookup and does not vectorise.

        Args:
            party_name: Extracted party name from a transaction description.

        Returns:
            Tuple of (party_id, confidence) where confidence is 0–100.
            Exact matches return 100. New parties also return 100 (they are
            correct by definition — just uncategorized).

        Raises:
            ValueError: If `party_name` is empty or whitespace.

        Side effects:
            - Fuzzy matches add a new alias to `self.alias_mapping` (and DB).
            - Unmatched names create a new party in the DB.
            - `new_aliases` / `new_parties` counters are incremented.
        """
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

    def find_matches_batch(self, party_names: pd.Series) -> pd.DataFrame:
        """
        Identify parties for a Series of description strings.

        Significantly faster than calling `find_match()` in a loop because:
        - Deduplication means each unique name is processed exactly once,
            regardless of how many transactions share that merchant.
        - Exact lookup is a vectorised dict `.map` rather than a Python loop.
        - Fuzzy matching uses `process.cdist` with `workers=-1` (all CPU
            cores) rather than sequential `extractOne` calls.
        - New parties are inserted in a single DB transaction rather than
            one INSERT per unknown name.

        Steps:
        1. Deduplicate → only unique names enter the matching pipeline.
        2. Exact match → bulk dict lookup; hits skip fuzzy entirely.
        3. Fuzzy match → `cdist` produces a (names × aliases) score matrix;
            the best-scoring alias per row is taken. Matches above threshold
            are accepted and their name added as a new alias.
        4. New parties → names below threshold are bulk-inserted in one
            transaction, then added to the in-memory alias map.
        5. Broadcast → results mapped back to the original (non-deduplicated)
            Series index.

        Args:
            party_names: Series of extracted party name strings, one per
                transaction. May contain duplicates.

        Returns:
            DataFrame aligned to `party_names.index` with columns:
            - `cleaned_description` — the input name (pass-through)
            - `party_id`            — matched or newly created party id,
                                        or None for blank inputs
            - `confidence`          — 0–100; 100 for exact/new, fuzzy score
                                        for fuzzy matches, 0 for blanks

        Side effects:
            Updates `self.alias_mapping`, `self.new_aliases`, `self.new_parties`.
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