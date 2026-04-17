# tests/test_categorizer/test_transaction_categorizer.py
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

    def test_result_length_matches_input_length(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"] * 7)
        assert len(result) == 7

    def test_resets_matcher_counters_per_call(self, make_categorizer):
        cat = make_categorizer()
        cat.categorize(["AMAZON"])           # creates 1 new party
        assert cat.matcher.new_parties == 1

        cat.categorize(["AMAZON"])           # exact match this time
        assert cat.matcher.new_parties == 0  # reset at start of call

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
        assert r2[0]["confidence"] == 100
        assert r2[1]["confidence"] == 100


# ════════════════════════════════════════════════════════════════════
# Pipeline wiring — mock everything, verify data flows
#   clean_batch → extract_party_names_batch → find_matches_batch
# ════════════════════════════════════════════════════════════════════

class TestCategorizeWiring:
    """
    Pure orchestration tests. Extractor and matcher are mocked so these
    don't depend on PartyExtractor's actual cleaning rules.
    """

    def _build(self, cleaned, extracted, match_df):
        """Helper: patch both dependencies and return a categorizer + mocks."""
        ext_patch = patch(
            "src.categorizer.transaction_categorizer.PartyExtractor"
        )
        match_patch = patch(
            "src.categorizer.transaction_categorizer.get_party_matcher"
        )
        mock_ext_cls = ext_patch.start()
        mock_get_matcher = match_patch.start()

        extractor = Mock()
        extractor.clean_batch.return_value = pd.Series(cleaned)
        extractor.extract_party_names_batch.return_value = pd.Series(extracted)
        mock_ext_cls.return_value = extractor

        matcher = Mock()
        matcher.find_matches_batch.return_value = match_df
        matcher.get_new_counts.return_value = (0, 0)
        mock_get_matcher.return_value = matcher

        cat = TransactionCategorizer()
        return cat, extractor, matcher, (ext_patch, match_patch)

    def test_stages_called_in_order_with_flowing_data(self):
        match_df = pd.DataFrame([
            {"cleaned_description": "EXTRACTED", "party_id": 1, "confidence": 100}
        ])
        cat, extractor, matcher, patches = self._build(
            cleaned=["CLEANED"], extracted=["EXTRACTED"], match_df=match_df
        )
        try:
            result = cat.categorize(["RAW DESC"])

            # Stage 1: clean_batch receives raw input as a Series
            arg = extractor.clean_batch.call_args[0][0]
            assert list(arg) == ["RAW DESC"]

            # Stage 2: extract receives cleaned output
            arg = extractor.extract_party_names_batch.call_args[0][0]
            assert list(arg) == ["CLEANED"]

            # Stage 3: matcher receives extracted output
            arg = matcher.find_matches_batch.call_args[0][0]
            assert list(arg) == ["EXTRACTED"]

            # Result is the matcher's DataFrame as records
            assert result == match_df.to_dict("records")
        finally:
            for p in patches:
                p.stop()

    def test_blank_after_clean_becomes_unknown(self):
        """Rows that clean to '' are replaced with 'UNKNOWN' before matching."""
        match_df = pd.DataFrame([
            {"cleaned_description": "WALMART", "party_id": 1, "confidence": 100},
            {"cleaned_description": "UNKNOWN", "party_id": 99, "confidence": 100},
        ])
        cat, extractor, matcher, patches = self._build(
            cleaned=["WALMART", ""],          # second row cleans to empty
            extracted=["WALMART", "GARBAGE"], # extractor output is overridden
            match_df=match_df,
        )
        try:
            cat.categorize(["POS WALMART", "*** 1234"])
            sent_to_matcher = list(matcher.find_matches_batch.call_args[0][0])
            assert sent_to_matcher == ["WALMART", "UNKNOWN"]
        finally:
            for p in patches:
                p.stop()

    def test_reset_counts_called(self):
        match_df = pd.DataFrame(
            [{"cleaned_description": "X", "party_id": 1, "confidence": 100}]
        )
        cat, _, matcher, patches = self._build(
            cleaned=["X"], extracted=["X"], match_df=match_df
        )
        try:
            cat.categorize(["X"])
            matcher.reset_counts.assert_called_once()
        finally:
            for p in patches:
                p.stop()


# ════════════════════════════════════════════════════════════════════
# End-to-end with real PartyExtractor (light touch)
# ════════════════════════════════════════════════════════════════════

class TestCategorizePipeline:
    """
    Uses the real PartyExtractor. These assertions depend on its
    cleaning/extraction rules — adjust if extractor behaviour changes.
    """

    def test_prefix_and_noise_stripped(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1}, similarity_threshold=70)
        result = cat.categorize(["PAYMENT TO WALMART 12/25/2023"])
        assert result[0]["party_id"] == 1

    def test_large_batch_with_duplicates(self, make_categorizer):
        cat = make_categorizer({"WALMART": 1})
        result = cat.categorize(["WALMART"] * 500 + ["AMAZON"] * 500)
        assert len(result) == 1000
        assert sum(1 for r in result if r["party_id"] == 1) == 500