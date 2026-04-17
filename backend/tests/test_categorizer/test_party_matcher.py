# tests/test_categorizer/test_party_matcher.py
import pytest

import pandas as pd

from src.categorizer.party_matcher import PartyMatcher
from src.categorizer.party_matcher_raw import PartyMatcherRaw


# ════════════════════════════════════════════════════════════════════
# Initialisation
# ════════════════════════════════════════════════════════════════════

class TestPartyMatcherRawInitialization:
    """PartyMatcherRaw.__init__ — no DB needed."""

    def test_default_threshold(self):
        matcher = PartyMatcherRaw()
        assert matcher.similarity_threshold == 70

    def test_custom_threshold(self):
        matcher = PartyMatcherRaw(similarity_threshold=85)
        assert matcher.similarity_threshold == 85

    @pytest.mark.parametrize("threshold", [0, 100])
    def test_boundary_thresholds_accepted(self, threshold):
        matcher = PartyMatcherRaw(similarity_threshold=threshold)
        assert matcher.similarity_threshold == threshold

    @pytest.mark.parametrize("threshold", [-1, -100, 101, 1000])
    def test_out_of_range_threshold_raises(self, threshold):
        with pytest.raises(ValueError, match="between 0 and 100"):
            PartyMatcherRaw(similarity_threshold=threshold)

    def test_initial_state_is_empty(self):
        matcher = PartyMatcherRaw()
        assert matcher.alias_mapping == {}
        assert matcher._alias_keys == []
        assert matcher.last_match_score == 0
        assert matcher.new_aliases == 0
        assert matcher.new_parties == 0


class TestPartyMatcherInitialization:
    """PartyMatcher.__init__ — DB-backed, uses FakeCategoryRepository."""

    def test_uses_injected_db(self, fake_repo):
        matcher = PartyMatcher(db=fake_repo)
        assert matcher.db is fake_repo

    def test_loads_aliases_from_db(self, make_matcher):
        matcher, _ = make_matcher({"WALMART": 1, "TARGET": 2})
        assert matcher.alias_mapping == {"WALMART": 1, "TARGET": 2}
        assert set(matcher._alias_keys) == {"WALMART", "TARGET"}

    def test_normalises_alias_keys_on_load(self, make_matcher):
        matcher, _ = make_matcher({"walmart": 1, "  Tesco   Metro ": 2})
        assert "WALMART" in matcher.alias_mapping
        assert "TESCO METRO" in matcher.alias_mapping

    def test_drops_blank_aliases_on_load(self, make_matcher):
        matcher, _ = make_matcher({"": 1, "   ": 2, "WALMART": 3})
        assert matcher.alias_mapping == {"WALMART": 3}


# ════════════════════════════════════════════════════════════════════
# Normalization
# ════════════════════════════════════════════════════════════════════

class TestNormalize:
    """PartyMatcher._normalize — static, no fixtures needed."""

    @pytest.mark.parametrize("input_val, expected", [
        ("walmart", "WALMART"),
        ("WALMART", "WALMART"),
        ("Walmart", "WALMART"),
        ("  spaced  out  ", "SPACED OUT"),
        ("\ttabs\nand\nnewlines", "TABS AND NEWLINES"),
        ("", ""),
        ("   ", ""),
    ])
    def test_normalize(self, input_val, expected):
        assert PartyMatcher._normalize(input_val) == expected

    def test_normalize_none_returns_empty(self):
        assert PartyMatcher._normalize(None) == ""


# ════════════════════════════════════════════════════════════════════
# Exact match
# ════════════════════════════════════════════════════════════════════

class TestCheckExactMatch:
    """_check_exact_match — operates on alias_mapping after normalisation."""

    def test_exact_hit(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        assert m._check_exact_match("WALMART") == 1

    def test_case_insensitive_via_normalize(self, raw_matcher):
        """find_match normalises before calling _check_exact_match.
        _check_exact_match itself is a raw dict lookup, so we verify
        that the key stored is already normalised."""
        m = raw_matcher({"walmart": 1})          # fixture normalises
        assert m._check_exact_match("WALMART") == 1

    def test_miss_raises_keyerror(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        with pytest.raises(KeyError, match="TARGET"):
            m._check_exact_match("TARGET")

    def test_empty_mapping_raises_keyerror(self, raw_matcher):
        m = raw_matcher()
        with pytest.raises(KeyError):
            m._check_exact_match("ANYTHING")

    def test_multiple_aliases_same_party(self, raw_matcher):
        m = raw_matcher({"WALMART": 1, "WAL-MART": 1, "WALMART STORE": 1})
        assert m._check_exact_match("WALMART") == 1
        assert m._check_exact_match("WAL-MART") == 1
        assert m._check_exact_match("WALMART STORE") == 1


# ════════════════════════════════════════════════════════════════════
# Fuzzy match
# ════════════════════════════════════════════════════════════════════

class TestCheckFuzzyMatch:

    def test_similar_name_matches(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        party_id, score = m._check_fuzzy_match("WALMART STORE")
        assert party_id == 1
        assert score >= 70

    def test_match_updates_last_match_score(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        _, score = m._check_fuzzy_match("WALMART STORE")
        assert m.last_match_score == score

    def test_match_adds_alias_to_mapping(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        m._check_fuzzy_match("WALMART STORE")
        assert "WALMART STORE" in m.alias_mapping
        assert m.new_aliases == 1

    def test_existing_alias_not_re_added(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        # First fuzzy call adds it
        m._check_fuzzy_match("WALMART STORE")
        count_after_first = m.new_aliases
        # Second call — already in mapping, counter unchanged
        m._check_fuzzy_match("WALMART STORE")
        assert m.new_aliases == count_after_first

    def test_below_threshold_raises_keyerror(self, raw_matcher):
        m = raw_matcher({"WALMART": 1}, similarity_threshold=95)
        with pytest.raises(KeyError, match="above threshold"):
            m._check_fuzzy_match("COMPLETELY DIFFERENT STORE")

    def test_empty_mapping_raises_lookuperror(self, raw_matcher):
        m = raw_matcher()
        with pytest.raises(LookupError, match="No known parties"):
            m._check_fuzzy_match("WALMART")

    def test_typo_still_matches(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        party_id, score = m._check_fuzzy_match("WALMRT")
        assert party_id == 1
        assert score >= 70

    def test_best_candidate_wins(self, raw_matcher):
        m = raw_matcher({"WALMART": 1, "TARGET": 2})
        party_id, _ = m._check_fuzzy_match("WALMART STORE")
        assert party_id == 1


# ════════════════════════════════════════════════════════════════════
# find_match (public scalar API)
# ════════════════════════════════════════════════════════════════════

class TestFindMatch:

    # ── exact path ──

    def test_exact_match_returns_100(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        party_id, confidence = m.find_match("WALMART")
        assert party_id == 1
        assert confidence == 100
        assert m.last_match_score == 100

    def test_exact_match_case_insensitive(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        party_id, confidence = m.find_match("walmart")
        assert party_id == 1
        assert confidence == 100

    # ── fuzzy path ──

    def test_fuzzy_match_returns_score(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        party_id, confidence = m.find_match("WALMART STORE")
        assert party_id == 1
        assert 70 <= confidence < 100

    def test_fuzzy_match_becomes_exact_on_repeat(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        m.find_match("WALMART STORE")
        assert m.last_match_score < 100

        _, confidence = m.find_match("WALMART STORE")
        assert confidence == 100

    # ── new-party path ──

    def test_no_match_creates_new_party(self, raw_matcher):
        m = raw_matcher()
        party_id, confidence = m.find_match("NEW VENDOR")
        assert party_id is not None
        assert confidence == 100
        assert m.new_parties == 1

    def test_new_party_then_exact_on_repeat(self, raw_matcher):
        m = raw_matcher()
        first_id, _ = m.find_match("NEW VENDOR")
        second_id, confidence = m.find_match("NEW VENDOR")
        assert second_id == first_id
        assert confidence == 100

    def test_multiple_new_parties_get_distinct_ids(self, raw_matcher):
        m = raw_matcher()
        id_a, _ = m.find_match("VENDOR A")
        id_b, _ = m.find_match("STORE B")
        id_c, _ = m.find_match("SHOP C")
        assert len({id_a, id_b, id_c}) == 3
        assert m.new_parties == 3

    # ── input validation ──

    @pytest.mark.parametrize("bad_input", ["", "   ", "\t\n", None])
    def test_blank_input_raises_valueerror(self, raw_matcher, bad_input):
        m = raw_matcher()
        with pytest.raises(ValueError, match="No party name provided"):
            m.find_match(bad_input)

    # ── counters ──

    def test_new_aliases_counter(self, raw_matcher):
        m = raw_matcher({"WALMART": 1})
        m.find_match("WALMART STORE")
        assert m.new_aliases == 1
        assert m.new_parties == 0

    def test_new_parties_counter(self, raw_matcher):
        m = raw_matcher()
        m.find_match("AMAZON")
        m.find_match("NETFLIX")
        assert m.new_parties == 2
        assert m.new_aliases == 0

    def test_reset_counts(self, raw_matcher):
        m = raw_matcher()
        m.find_match("VENDOR")
        m.reset_counts()
        assert m.get_new_counts() == (0, 0)


# ════════════════════════════════════════════════════════════════════
# Custom scorer
# ════════════════════════════════════════════════════════════════════

class TestCustomScorer:
    """PartyMatcher.custom_scorer — static, no fixtures needed."""

    def test_identical_strings_score_100(self):
        assert PartyMatcher.custom_scorer("WALMART", "WALMART") == 100

    def test_completely_different_strings_score_low(self):
        assert PartyMatcher.custom_scorer("WALMART", "ZZZZZZZ") < 30

    def test_partial_match_boosted(self):
        """A substring match should score higher than char-level alone."""
        score = PartyMatcher.custom_scorer("WALMART", "WALMART STORE #123")
        assert score >= 70

    def test_score_cutoff_returns_zero_when_below(self):
        score = PartyMatcher.custom_scorer("WALMART", "ZZZZZZZ", score_cutoff=90)
        assert score == 0

    def test_score_cutoff_passes_when_above(self):
        score = PartyMatcher.custom_scorer("WALMART", "WALMART", score_cutoff=90)
        assert score >= 90


# ════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_special_characters(self, raw_matcher):
        m = raw_matcher()
        party_id, _ = m.find_match("WAL*MART #123 @STORE")
        assert party_id is not None

    def test_unicode_characters(self, raw_matcher):
        m = raw_matcher()
        party_id, _ = m.find_match("Café München")
        assert party_id is not None

    def test_single_character(self, raw_matcher):
        m = raw_matcher()
        party_id, _ = m.find_match("A")
        assert party_id is not None

    def test_very_long_name(self, raw_matcher):
        m = raw_matcher()
        party_id, _ = m.find_match("WALMART " * 100)
        assert party_id is not None

    def test_threshold_zero_always_fuzzy_matches(self, raw_matcher):
        m = raw_matcher({"WALMART": 1}, similarity_threshold=0)
        party_id, _ = m.find_match("COMPLETELY DIFFERENT")
        assert party_id == 1

    def test_threshold_100_rejects_near_miss(self, raw_matcher):
        m = raw_matcher({"WALMART": 1}, similarity_threshold=100)
        party_id, _ = m.find_match("WALM ART")
        # Can't fuzzy‑match at 100 — falls through to new party
        assert party_id != 1

    def test_multiple_matchers_independent(self, raw_matcher):
        m1 = raw_matcher()
        m2 = raw_matcher()
        m1.find_match("WALMART")
        assert "WALMART" in m1.alias_mapping
        assert "WALMART" not in m2.alias_mapping


# ════════════════════════════════════════════════════════════════════
# DB delegation (parent PartyMatcher, not Raw)
# ════════════════════════════════════════════════════════════════════

class TestPartyMatcherDbWrites:
    """
    Cover the PartyMatcher methods that PartyMatcherRaw overrides,
    so the parent implementations actually execute.
    """

    def test_find_match_new_party_writes_to_repo(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1})
        pid, conf = matcher.find_match("AMAZON")

        assert pid == 2
        assert conf == 100
        assert repo.added_parties == ["AMAZON"]
        assert matcher.new_parties == 1
        assert "AMAZON" in matcher.alias_mapping

    def test_find_match_fuzzy_does_not_write_to_repo(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1})
        matcher.find_match("WALMART STORE")

        assert repo.added_parties == []
        assert matcher.new_aliases == 1


# ════════════════════════════════════════════════════════════════════
# find_matches_batch
# ════════════════════════════════════════════════════════════════════

class TestFindMatchesBatch:

    def test_result_shape_and_index_alignment(self, make_matcher):
        matcher, _ = make_matcher({"WALMART": 1})
        names = pd.Series(["WALMART", "WALMART"], index=[10, 20])

        df = matcher.find_matches_batch(names)

        assert list(df.index) == [10, 20]
        assert list(df.columns) == [
            "cleaned_description", "party_id", "confidence"
        ]

    def test_all_exact_matches(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1, "TARGET": 2})
        names = pd.Series(["WALMART", "TARGET", "WALMART"])

        df = matcher.find_matches_batch(names)

        assert df["party_id"].tolist() == [1, 2, 1]
        assert (df["confidence"] == 100).all()
        assert repo.bulk_added_parties == []
        assert repo.prime_cache_calls == 0   # no fuzzy step needed

    def test_fuzzy_match_adds_alias_not_party(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1, "TARGET": 2})
        names = pd.Series(["WALMART STORE 123"])

        df = matcher.find_matches_batch(names)

        assert df["party_id"].iloc[0] == 1
        assert 70 <= df["confidence"].iloc[0] < 100
        assert "WALMART STORE 123" in matcher.alias_mapping
        assert matcher.new_aliases == 1
        assert repo.bulk_added_parties == []

    def test_unmatched_names_bulk_inserted_once(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1})
        names = pd.Series(["AMAZON", "NETFLIX"])

        df = matcher.find_matches_batch(names)

        assert len(repo.bulk_added_parties) == 1
        assert set(repo.bulk_added_parties[0]) == {"AMAZON", "NETFLIX"}
        assert set(df["party_id"]) == {2, 3}
        assert (df["confidence"] == 100).all()
        assert matcher.new_parties == 2

    def test_cold_start_everything_is_new(self, make_matcher):
        """No known aliases — exercises the `not self._alias_keys` branch."""
        matcher, repo = make_matcher()
        names = pd.Series(["AMAZON", "NETFLIX"])

        df = matcher.find_matches_batch(names)

        assert matcher.new_parties == 2
        assert df["party_id"].notna().all()

    def test_duplicates_processed_once(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1})
        names = pd.Series(["AMAZON"] * 5)

        df = matcher.find_matches_batch(names)

        assert repo.bulk_added_parties == [["AMAZON"]]
        assert (df["party_id"] == 2).all()

    def test_blank_inputs_map_to_none(self, make_matcher):
        matcher, _ = make_matcher({"WALMART": 1})
        names = pd.Series(["WALMART", "", "   "])

        df = matcher.find_matches_batch(names)

        assert df["party_id"].iloc[0] == 1
        assert pd.isna(df["party_id"].iloc[1])
        assert df["confidence"].iloc[1] == 0
        assert pd.isna(df["party_id"].iloc[2])
        assert df["confidence"].iloc[2] == 0

    def test_primes_cache_only_when_fuzzy_runs(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1})
        matcher.find_matches_batch(pd.Series(["AMAZON"]))
        assert repo.prime_cache_calls == 1

    def test_mixed_exact_fuzzy_new(self, make_matcher):
        matcher, repo = make_matcher({"WALMART": 1, "TARGET": 2})
        names = pd.Series([
            "WALMART",            # exact → 1
            "WALMART STORE 123",  # fuzzy → 1
            "TARGET",             # exact → 2
            "AMAZON",             # new   → 3
            "WALMART",            # dup exact
        ])

        df = matcher.find_matches_batch(names)

        assert df["party_id"].tolist() == [1, 1, 2, 3, 1]
        assert df["confidence"].iloc[0] == 100
        assert 70 <= df["confidence"].iloc[1] < 100
        assert df["confidence"].iloc[3] == 100
        assert matcher.new_aliases == 1
        assert matcher.new_parties == 1


# ════════════════════════════════════════════════════════════════════
# PartyMatcherReadOnly
# ════════════════════════════════════════════════════════════════════

class TestPartyMatcherReadOnly:

    def test_exact_match(self, make_readonly_matcher):
        m, _ = make_readonly_matcher({"WALMART": 1})
        assert m.find_match("WALMART") == (1, 100)

    def test_fuzzy_match(self, make_readonly_matcher):
        m, _ = make_readonly_matcher({"WALMART": 1})
        pid, score = m.find_match("WALMART STORE")
        assert pid == 1
        assert 70 <= score < 100

    def test_no_match_returns_none_and_no_db_write(self, make_readonly_matcher):
        m, repo = make_readonly_matcher({"WALMART": 1})
        assert m.find_match("AMAZON") is None
        assert repo.added_parties == []
        assert repo.bulk_added_parties == []

    def test_no_known_parties_returns_none(self, make_readonly_matcher):
        m, repo = make_readonly_matcher()
        assert m.find_match("ANYTHING") is None
        assert repo.added_parties == []

    def test_add_unknown_party_is_noop(self, make_readonly_matcher):
        m, repo = make_readonly_matcher()
        assert m._add_unknown_party("X") is None
        assert repo.added_parties == []

    @pytest.mark.parametrize("bad", ["", "   ", "\t", None])
    def test_blank_input_raises(self, make_readonly_matcher, bad):
        m, _ = make_readonly_matcher()
        with pytest.raises(ValueError):
            m.find_match(bad)