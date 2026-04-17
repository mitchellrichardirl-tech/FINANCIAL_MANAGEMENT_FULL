import pandas as pd
import pytest

from src.categorizer.party_extractor import PartyExtractor


# ════════════════════════════════════════════════════════════════════
# Initialisation
# ════════════════════════════════════════════════════════════════════

class TestPartyExtractorInit:

    def test_default_patterns_loaded(self, extractor):
        assert len(extractor.patterns) == len(PartyExtractor.DEFAULT_PATTERNS)
        assert len(extractor._compiled_patterns) == len(extractor.patterns)

    def test_default_stop_words_loaded(self, extractor):
        assert extractor.stop_words == PartyExtractor.DEFAULT_STOP_WORDS

    def test_custom_patterns_appended(self):
        custom = [r'\bFOO\b']
        ext = PartyExtractor(custom_patterns=custom)
        assert len(ext.patterns) == len(PartyExtractor.DEFAULT_PATTERNS) + 1
        assert ext.patterns[-1] == r'\bFOO\b'

    def test_custom_stop_words_merged(self):
        custom = {"XYZZY", "PLUGH"}
        ext = PartyExtractor(custom_stop_words=custom)
        assert "XYZZY" in ext.stop_words
        assert "PLUGH" in ext.stop_words
        # originals still present
        assert "LTD" in ext.stop_words

    def test_none_custom_args_safe(self):
        ext = PartyExtractor(custom_patterns=None, custom_stop_words=None)
        assert len(ext.patterns) == len(PartyExtractor.DEFAULT_PATTERNS)
        assert ext.stop_words == PartyExtractor.DEFAULT_STOP_WORDS


# ════════════════════════════════════════════════════════════════════
# clean() — scalar
# ════════════════════════════════════════════════════════════════════

class TestClean:

    # ── Prefix stripping ──

    @pytest.mark.parametrize("prefix", [
        "PAYMENT TO",
        "TRANSFER TO",
        "TRANSFER FROM",
        "PURCHASE AT",
        "POS TRANSACTION",
        "ONLINE PAYMENT",
        "DIRECT DEBIT",
        "DIRECT CREDIT",
        "DEBIT CARD",
        "CREDIT CARD",
    ])
    def test_long_prefixes_stripped(self, extractor, prefix):
        result = extractor.clean(f"{prefix} TESCO")
        assert "TESCO" in result
        for word in prefix.split():
            assert word not in result.split()

    @pytest.mark.parametrize("prefix", [
        "POS", "CNC", "TKN", "DD", "CT", "VPP", "INET", "Rtd",
    ])
    def test_short_prefixes_stripped(self, extractor, prefix):
        result = extractor.clean(f"{prefix} TESCO")
        assert "TESCO" in result

    @pytest.mark.parametrize("prefix", [
        "PAYMENT", "TRANSFER", "PURCHASE", "DEBIT", "CREDIT",
    ])
    def test_single_word_prefixes_stripped(self, extractor, prefix):
        result = extractor.clean(f"{prefix} TESCO")
        assert "TESCO" in result

    # ── Trailing date / time stripping ──

    @pytest.mark.parametrize("suffix", [
        "12/25/2023",
        "12/25/23",
        "25/12 14:30",
        "25/12 9",
        "25-12-2023",
        "14:30",
    ])
    def test_trailing_dates_and_times_stripped(self, extractor, suffix):
        result = extractor.clean(f"TESCO {suffix}")
        assert "TESCO" in result
        # No digits from the suffix should survive
        assert not any(c.isdigit() for c in result)

    # ── Trailing reference / card / store codes ──

    @pytest.mark.parametrize("suffix", [
        "123456",       # long number
        "REF:ABC123",   # reference
        "****1234",     # masked card
        "123",          # short number
        "A12",          # letter + digits
        "#456",         # hash code
    ])
    def test_trailing_codes_stripped(self, extractor, suffix):
        result = extractor.clean(f"TESCO {suffix}")
        assert "TESCO" in result

    # ── Normalisation ──

    def test_output_is_uppercase(self, extractor):
        assert extractor.clean("tesco metro") == "TESCO METRO"

    def test_whitespace_collapsed(self, extractor):
        assert extractor.clean("TESCO   METRO   STORE") == "TESCO METRO STORE"

    def test_punctuation_replaced_with_space(self, extractor):
        result = extractor.clean("WAL*MART")
        assert "*" not in result
        # Core name survives in some form
        assert "WAL" in result

    def test_standalone_single_letters_removed(self, extractor):
        result = extractor.clean("TESCO A METRO")
        words = result.split()
        assert "A" not in words

    # ── Null / empty handling ──

    def test_none_returns_empty(self, extractor):
        assert extractor.clean(None) == ""

    def test_nan_returns_empty(self, extractor):
        assert extractor.clean(float("nan")) == ""

    def test_empty_string_returns_empty(self, extractor):
        assert extractor.clean("") == ""

    def test_whitespace_only_returns_empty(self, extractor):
        assert extractor.clean("   ") == ""

    # ── Compound / realistic descriptions ──

    def test_full_description_cleaned(self, extractor):
        raw = "POS TRANSACTION TESCO METRO RATHMINES 12/03/24 REF:98765"
        result = extractor.clean(raw)
        assert "TESCO" in result
        assert "METRO" in result
        assert "REF" not in result
        assert "12" not in result

    def test_multiple_noise_layers(self, extractor):
        raw = "PAYMENT TO WALMART SUPERCENTER ****1234 12/25/2023"
        result = extractor.clean(raw)
        assert "WALMART" in result
        assert "****" not in result


# ════════════════════════════════════════════════════════════════════
# extract_party_name() — scalar
# ════════════════════════════════════════════════════════════════════

class TestExtractPartyName:

    # ── Basic extraction ──

    def test_simple_name_passes_through(self, extractor):
        assert extractor.extract_party_name("TESCO") == "TESCO"

    def test_multi_word_name(self, extractor):
        assert extractor.extract_party_name("TESCO METRO RATHMINES") == "TESCO METRO RATHMINES"

    def test_max_words_default_is_3(self, extractor):
        result = extractor.extract_party_name("ALPHA BRAVO CHARLIE DELTA ECHO")
        assert len(result.split()) == 3
        assert result == "ALPHA BRAVO CHARLIE"

    def test_max_words_custom(self, extractor):
        result = extractor.extract_party_name(
            "ALPHA BRAVO CHARLIE DELTA", max_words=2
        )
        assert result == "ALPHA BRAVO"

    # ── Stop word removal ──

    @pytest.mark.parametrize("stop_word", [
        "LTD", "LIMITED", "INC", "CORP", "LLC",
        "STORE", "STORES", "CARD", "VISA",
        "DUBLIN", "IRELAND",
        "THE", "AND", "FOR",
        "PAYMENT", "TRANSFER", "DEBIT",
    ])
    def test_stop_words_removed(self, extractor, stop_word):
        result = extractor.extract_party_name(f"{stop_word} TESCO {stop_word}")
        assert stop_word not in result.split()
        assert "TESCO" in result

    def test_single_char_tokens_removed(self, extractor):
        result = extractor.extract_party_name("A TESCO B METRO C")
        words = result.split()
        assert all(len(w) > 1 for w in words)
        assert "TESCO" in words

    # ── Fallback behaviour ──

    def test_empty_returns_unknown(self, extractor):
        assert extractor.extract_party_name("") == "UNKNOWN"

    def test_none_returns_unknown(self, extractor):
        # clean() returns "" for None, which then feeds here
        assert extractor.extract_party_name("") == "UNKNOWN"

    def test_all_stop_words_falls_back_to_truncation(self, extractor):
        """If every word is a stop word, fall back to first 30 chars."""
        input_text = "THE AND FOR"
        result = extractor.extract_party_name(input_text)
        # Nothing meaningful survived, so fallback kicks in
        assert result == input_text  # under 30 chars, returned as-is

    def test_long_all_stop_words_truncated_to_30(self, extractor):
        input_text = " ".join(["THE"] * 20)  # 79 chars
        result = extractor.extract_party_name(input_text)
        assert len(result) <= 30

    # ── Clean → extract two-step contract ──

    def test_clean_then_extract_realistic(self, extractor):
        """The documented two-step usage pattern."""
        raw = "POS TRANSACTION TESCO METRO RATHMINES 12/03/24 REF:98765"
        cleaned = extractor.clean(raw)
        party = extractor.extract_party_name(cleaned)
        assert "TESCO" in party
        assert "METRO" in party

    def test_clean_then_extract_noisy(self, extractor):
        raw = "PAYMENT TO WALMART SUPERCENTER ****1234 12/25/2023"
        cleaned = extractor.clean(raw)
        party = extractor.extract_party_name(cleaned)
        assert "WALMART" in party


# ════════════════════════════════════════════════════════════════════
# clean_batch() — vectorised
# ════════════════════════════════════════════════════════════════════

class TestCleanBatch:

    def test_matches_scalar_clean(self, extractor):
        descriptions = [
            "PAYMENT TO TESCO 12/25/2023",
            "POS WALMART ****1234",
            "DIRECT DEBIT NETFLIX REF:ABC",
        ]
        series = pd.Series(descriptions)
        batch_result = extractor.clean_batch(series)

        for i, desc in enumerate(descriptions):
            assert batch_result.iloc[i] == extractor.clean(desc)

    def test_handles_nan_and_none(self, extractor):
        series = pd.Series([None, float("nan"), "TESCO"])
        result = extractor.clean_batch(series)
        assert result.iloc[0] == ""
        assert result.iloc[1] == ""
        assert "TESCO" in result.iloc[2]

    def test_returns_series_same_length(self, extractor):
        series = pd.Series(["A", "B", "C"])
        result = extractor.clean_batch(series)
        assert len(result) == 3

    def test_preserves_index(self, extractor):
        series = pd.Series(["TESCO"], index=[42])
        result = extractor.clean_batch(series)
        assert list(result.index) == [42]


# ════════════════════════════════════════════════════════════════════
# extract_party_names_batch() — vectorised
# ════════════════════════════════════════════════════════════════════

class TestExtractPartyNamesBatch:

    def test_matches_scalar_extract(self, extractor):
        cleaned = ["TESCO METRO RATHMINES", "WALMART SUPERCENTER", "NETFLIX"]
        series = pd.Series(cleaned)
        batch_result = extractor.extract_party_names_batch(series)

        for i, desc in enumerate(cleaned):
            assert batch_result.iloc[i] == extractor.extract_party_name(desc)

    def test_empty_input_becomes_unknown(self, extractor):
        series = pd.Series(["", "  "])
        result = extractor.extract_party_names_batch(series)
        assert (result == "UNKNOWN").all()

    def test_returns_series_same_length(self, extractor):
        series = pd.Series(["TESCO", "WALMART", "AMAZON"])
        result = extractor.extract_party_names_batch(series)
        assert len(result) == 3

    def test_preserves_index(self, extractor):
        series = pd.Series(["TESCO"], index=[42])
        result = extractor.extract_party_names_batch(series)
        assert list(result.index) == [42]

    def test_max_words_respected(self, extractor):
        series = pd.Series(["ALPHA BRAVO CHARLIE DELTA ECHO"])
        result = extractor.extract_party_names_batch(series, max_words=2)
        assert len(result.iloc[0].split()) <= 2

    def test_stop_words_stripped(self, extractor):
        series = pd.Series(["TESCO LTD DUBLIN"])
        result = extractor.extract_party_names_batch(series)
        words = result.iloc[0].split()
        assert "LTD" not in words
        assert "DUBLIN" not in words
        assert "TESCO" in words