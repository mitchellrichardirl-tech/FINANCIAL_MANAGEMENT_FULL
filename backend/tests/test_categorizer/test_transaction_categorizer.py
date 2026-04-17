import contextlib
import pytest
import pandas as pd
from unittest.mock import Mock, patch

from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.categorizer.party_extractor import PartyExtractor
from src.categorizer.party_matcher_raw import PartyMatcherRaw


# ════════════════════════════════════════════════════════════════════
# Initialisation
# ════════════════════════════════════════════════════════════════════

class TestTransactionCategorizerInitialization:

    def test_default_threshold_is_80(self):
        cat = TransactionCategorizer(use_db=False)
        assert cat.matcher.similarity_threshold == 80

    def test_custom_threshold_passed_through(self):
        cat = TransactionCategorizer(similarity_threshold=90, use_db=False)
        assert cat.matcher.similarity_threshold == 90

    @pytest.mark.parametrize("threshold", [-1, 101])
    def test_invalid_threshold_raises(self, threshold):
        with pytest.raises(ValueError):
            TransactionCategorizer(similarity_threshold=threshold, use_db=False)

    def test_use_db_false_selects_raw_matcher(self):
        cat = TransactionCategorizer(use_db=False)
        assert isinstance(cat.matcher, PartyMatcherRaw)

    def test_constructs_extractor(self):
        cat = TransactionCategorizer(use_db=False)
        assert isinstance(cat.extractor, PartyExtractor)

    def test_independent_instances(self):
        c1 = TransactionCategorizer(use_db=False)
        c2 = TransactionCategorizer(use_db=False)
        c1.matcher.alias_mapping["X"] = 1
        assert "X" not in c2.matcher.alias_mapping


# ════════════════════════════════════════════════════════════════════
# categorize() — orchestration logic that lives in this class
# ════════════════════════════════════════════════════════════════════

class TestCategorize:

    def test_empty_list_raises(self, make_categorizer):
        cat = make_categorizer()
        with pytest.raises(ValueError, match="No transactions data provided"):
            cat.categorize([])

    def test_returns_list_of_dicts_with_expected_keys(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert set(result[0].keys()) >= {
            "cleaned_description", "party_id", "confidence"
        }

    def test_preserves_input_order(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1, "TARGET": 2, "COSTCO": 3})
        result = cat.categorize(["COSTCO", "WALMART", "TARGET"])
        assert [r["party_id"] for r in result] == [3, 1, 2]

    def test_result_length_matches_input(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"] * 7)
        assert len(result) == 7

    def test_resets_matcher_counters_per_call(self, make_categorizer):
        cat = make_categorizer()
        cat.categorize(["AMAZON"])
        assert cat.matcher.new_parties == 1

        cat.categorize(["AMAZON"])  # exact hit this time
        assert cat.matcher.new_parties == 0

    def test_exact_match_confidence_100(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"])
        assert result[0]["party_id"] == 1
        assert result[0]["confidence"] == 100

    def test_unknown_party_is_created(self, make_categorizer):
        cat = make_categorizer()
        result = cat.categorize(["AMAZON"])
        assert result[0]["party_id"] is not None
        assert result[0]["confidence"] == 100
        assert cat.matcher.new_parties == 1

    def test_consistency_across_calls(self, make_categorizer):
        cat = make_categorizer()
        r1 = cat.categorize(["AMAZON", "NETFLIX"])
        r2 = cat.categorize(["AMAZON", "NETFLIX"])

        assert r1[0]["party_id"] == r2[0]["party_id"]
        assert r1[1]["party_id"] == r2[1]["party_id"]
        assert all(r["confidence"] == 100 for r in r2)

    def test_distinct_parties_get_distinct_ids(self, make_categorizer):
        cat = make_categorizer()
        result = cat.categorize(["AMAZON", "NETFLIX", "SPOTIFY"])
        ids = {r["party_id"] for r in result}
        assert len(ids) == 3

    def test_single_transaction(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"])
        assert len(result) == 1
        assert result[0]["party_id"] == 1


# ════════════════════════════════════════════════════════════════════
# Pipeline wiring — mock everything, verify data flows correctly
#   clean_batch → extract_party_names_batch → find_matches_batch
# ════════════════════════════════════════════════════════════════════

class TestCategorizeWiring:
    """
    Pure orchestration tests.  Extractor and matcher are mocked so
    results don't depend on PartyExtractor's cleaning rules.
    """

    @contextlib.contextmanager
    def _patched_categorizer(self, cleaned, extracted, match_df):
        """
        Build a TransactionCategorizer whose extractor and matcher are
        mocks returning the supplied canned values.

        Yields (categorizer, extractor_mock, matcher_mock).
        """
        with (
            patch("src.categorizer.transaction_categorizer.PartyExtractor") as ext_cls,
            patch("src.categorizer.transaction_categorizer.get_party_matcher") as get_matcher,
        ):
            extractor = Mock()
            extractor.clean_batch.return_value = pd.Series(cleaned)
            extractor.extract_party_names_batch.return_value = pd.Series(extracted)
            ext_cls.return_value = extractor

            matcher = Mock()
            matcher.find_matches_batch.return_value = match_df
            matcher.get_new_counts.return_value = (0, 0)
            get_matcher.return_value = matcher

            yield TransactionCategorizer(), extractor, matcher

    def test_stages_called_in_order_with_correct_data(self):
        match_df = pd.DataFrame([
            {"cleaned_description": "EXTRACTED", "party_id": 1, "confidence": 100}
        ])
        with self._patched_categorizer(
            cleaned=["CLEANED"],
            extracted=["EXTRACTED"],
            match_df=match_df,
        ) as (cat, extractor, matcher):

            result = cat.categorize(["RAW DESC"])

            assert list(extractor.clean_batch.call_args[0][0]) == ["RAW DESC"]
            assert list(extractor.extract_party_names_batch.call_args[0][0]) == ["CLEANED"]
            assert list(matcher.find_matches_batch.call_args[0][0]) == ["EXTRACTED"]
            assert result == match_df.to_dict("records")

    def test_blank_after_clean_becomes_unknown(self):
        """Rows that clean to '' are replaced with 'UNKNOWN' before matching."""
        match_df = pd.DataFrame([
            {"cleaned_description": "WALMART", "party_id": 1, "confidence": 100},
            {"cleaned_description": "UNKNOWN", "party_id": 99, "confidence": 100},
        ])
        with self._patched_categorizer(
            cleaned=["WALMART", ""],
            extracted=["WALMART", "GARBAGE"],
            match_df=match_df,
        ) as (cat, _, matcher):

            cat.categorize(["POS WALMART", "*** 1234"])
            sent = list(matcher.find_matches_batch.call_args[0][0])
            assert sent == ["WALMART", "UNKNOWN"]

    def test_reset_counts_called_before_matching(self):
        match_df = pd.DataFrame(
            [{"cleaned_description": "X", "party_id": 1, "confidence": 100}]
        )
        with self._patched_categorizer(
            cleaned=["X"], extracted=["X"], match_df=match_df,
        ) as (cat, _, matcher):

            cat.categorize(["X"])
            matcher.reset_counts.assert_called_once()

    def test_multiple_rows_flow_through(self):
        match_df = pd.DataFrame([
            {"cleaned_description": "A", "party_id": 1, "confidence": 100},
            {"cleaned_description": "B", "party_id": 2, "confidence": 100},
            {"cleaned_description": "C", "party_id": 3, "confidence": 100},
        ])
        with self._patched_categorizer(
            cleaned=["A", "B", "C"],
            extracted=["A", "B", "C"],
            match_df=match_df,
        ) as (cat, extractor, matcher):

            result = cat.categorize(["X", "Y", "Z"])
            assert len(result) == 3
            assert extractor.clean_batch.call_count == 1
            assert matcher.find_matches_batch.call_count == 1


# ════════════════════════════════════════════════════════════════════
# End-to-end with real PartyExtractor
#
# These depend on PartyExtractor's cleaning rules — if extraction
# behaviour changes, adjust the seeded aliases or inputs accordingly.
# ════════════════════════════════════════════════════════════════════

class TestCategorizePipeline:

    def test_prefix_and_date_stripped(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1}, similarity_threshold=70)
        result = cat.categorize(["PAYMENT TO WALMART 12/25/2023"])
        assert result[0]["party_id"] == 1

    def test_card_mask_stripped(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1}, similarity_threshold=70)
        result = cat.categorize(["POS WALMART ****1234"])
        assert result[0]["party_id"] == 1

    def test_ref_code_stripped(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1}, similarity_threshold=70)
        result = cat.categorize(["WALMART REF:ABC123"])
        assert result[0]["party_id"] == 1

    def test_large_batch_with_duplicates(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"] * 500 + ["AMAZON"] * 500)
        assert len(result) == 1000
        assert sum(1 for r in result if r["party_id"] == 1) == 500