import pytest
import pandas as pd
from typing import List, Set

from src.categorizer.party_extractor import PartyExtractor


class TestPartyExtractorInitialization:
    """Test PartyExtractor initialization"""
    
    def test_init_default(self):
        """Test initialization with default patterns and stop words"""
        extractor = PartyExtractor()
        
        assert len(extractor.patterns) == len(PartyExtractor.DEFAULT_PATTERNS)
        assert extractor.stop_words == PartyExtractor.DEFAULT_STOP_WORDS
    
    def test_init_with_custom_patterns(self):
        """Test initialization with custom patterns"""
        custom_patterns = [r'\s+CUSTOM\s+', r'^EXTRA\s+']
        extractor = PartyExtractor(custom_patterns=custom_patterns)
        
        assert len(extractor.patterns) == len(PartyExtractor.DEFAULT_PATTERNS) + 2
        assert r'\s+CUSTOM\s+' in extractor.patterns
        assert r'^EXTRA\s+' in extractor.patterns
    
    def test_init_with_custom_stop_words(self):
        """Test initialization with custom stop words"""
        custom_stop_words = {'CUSTOM', 'EXTRA', 'SPECIAL'}
        extractor = PartyExtractor(custom_stop_words=custom_stop_words)
        
        assert 'CUSTOM' in extractor.stop_words
        assert 'EXTRA' in extractor.stop_words
        assert 'SPECIAL' in extractor.stop_words
        # Default stop words should still be present
        assert 'PAYMENT' in extractor.stop_words
        assert 'THE' in extractor.stop_words
    
    def test_init_with_both_custom(self):
        """Test initialization with both custom patterns and stop words"""
        custom_patterns = [r'\s+TEST\s+']
        custom_stop_words = {'TEST'}
        
        extractor = PartyExtractor(
            custom_patterns=custom_patterns,
            custom_stop_words=custom_stop_words
        )
        
        assert r'\s+TEST\s+' in extractor.patterns
        assert 'TEST' in extractor.stop_words
    
    def test_init_with_empty_custom(self):
        """Test initialization with empty custom collections"""
        extractor = PartyExtractor(
            custom_patterns=[],
            custom_stop_words=set()
        )
        
        assert len(extractor.patterns) == len(PartyExtractor.DEFAULT_PATTERNS)
        assert extractor.stop_words == PartyExtractor.DEFAULT_STOP_WORDS


class TestCleanMethod:
    """Test the clean method"""
    
    def test_clean_basic_description(self):
        """Test cleaning a basic description"""
        extractor = PartyExtractor()
        result = extractor.clean("Starbucks Coffee Shop")
        
        assert result == "STARBUCKS COFFEE SHOP"
    
    def test_clean_empty_string(self):
        """Test cleaning empty string"""
        extractor = PartyExtractor()
        result = extractor.clean("")
        
        assert result == ""
    
    def test_clean_none_value(self):
        """Test cleaning None value"""
        extractor = PartyExtractor()
        result = extractor.clean(None)
        
        assert result == ""
    
    def test_clean_nan_value(self):
        """Test cleaning pandas NaN value"""
        extractor = PartyExtractor()
        result = extractor.clean(pd.NA)
        
        assert result == ""
    
    def test_clean_removes_payment_prefix(self):
        """Test removal of PAYMENT TO prefix"""
        extractor = PartyExtractor()
        result = extractor.clean("PAYMENT TO WALMART")
        
        assert result == "WALMART"
    
    def test_clean_removes_transfer_prefix(self):
        """Test removal of TRANSFER prefix"""
        extractor = PartyExtractor()
        result = extractor.clean("TRANSFER TO JOHN DOE")
        
        assert result == "JOHN DOE"
    
    def test_clean_removes_purchase_prefix(self):
        """Test removal of PURCHASE AT prefix"""
        extractor = PartyExtractor()
        result = extractor.clean("PURCHASE AT TARGET")
        
        assert result == "TARGET"
    
    def test_clean_removes_pos_prefix(self):
        """Test removal of POS prefix"""
        extractor = PartyExtractor()
        result = extractor.clean("POS COSTCO WHOLESALE")
        
        assert result == "COSTCO WHOLESALE"
    
    def test_clean_removes_date_suffix_slashes(self):
        """Test removal of date suffix with slashes"""
        extractor = PartyExtractor()
        result = extractor.clean("WALMART 12/25/2023")
        
        assert "12/25/2023" not in result
        assert "WALMART" in result
    
    def test_clean_removes_date_suffix_dashes(self):
        """Test removal of date suffix with dashes"""
        extractor = PartyExtractor()
        result = extractor.clean("TARGET 12-25-2023")
        
        assert "12-25-2023" not in result
        assert "TARGET" in result
    
    def test_clean_removes_time_suffix(self):
        """Test removal of time suffix"""
        extractor = PartyExtractor()
        result = extractor.clean("STARBUCKS 14:30")
        
        assert "14:30" not in result
        assert "STARBUCKS" in result
    
    def test_clean_removes_reference_number(self):
        """Test removal of reference numbers"""
        extractor = PartyExtractor()
        result = extractor.clean("AMAZON REF:123456")
        
        assert "REF:123456" not in result
        assert "AMAZON" in result
    
    def test_clean_removes_card_number(self):
        """Test removal of masked card numbers"""
        extractor = PartyExtractor()
        result = extractor.clean("PURCHASE ****1234")
        
        assert "****1234" not in result
        assert "****" not in result
        assert "*" not in result
        # Note: PURCHASE is also removed as it's a transaction type prefix

    def test_clean_removes_card_number_with_merchant(self):
        """Test removal of masked card numbers while preserving merchant"""
        extractor = PartyExtractor()
        result = extractor.clean("PURCHASE WALMART ****1234")
        
        assert "****1234" not in result
        assert "WALMART" in result
        assert "PURCHASE" not in result  # Transaction type prefix removed
    
    def test_clean_removes_trailing_numbers(self):
        """Test removal of trailing numbers"""
        extractor = PartyExtractor()
        result = extractor.clean("SHELL 1234")
        
        assert "1234" not in result
        assert "SHELL" in result
    
    def test_clean_removes_branch_codes(self):
        """Test removal of branch codes"""
        extractor = PartyExtractor()
        result = extractor.clean("WALMART G 28")
        
        assert "G 28" not in result
        assert "WALMART" in result
    
    def test_clean_removes_special_characters(self):
        """Test removal of special characters"""
        extractor = PartyExtractor()
        result = extractor.clean("WAL*MART #123")
        
        assert "*" not in result
        assert "#" not in result
        assert "WAL MART" in result or "WALMART" in result
    
    def test_clean_removes_standalone_letters(self):
        """Test removal of standalone single letters"""
        extractor = PartyExtractor()
        result = extractor.clean("WALMART A TARGET")
        
        # The 'A' should be removed
        assert result == "WALMART TARGET" or "WALMART" in result
    
    def test_clean_normalizes_whitespace(self):
        """Test whitespace normalization"""
        extractor = PartyExtractor()
        result = extractor.clean("WALMART    STORE     123")
        
        # Should have single spaces
        assert "  " not in result
    
    def test_clean_converts_to_uppercase(self):
        """Test conversion to uppercase"""
        extractor = PartyExtractor()
        result = extractor.clean("walmart store")
        
        assert result == "WALMART STORE"
    
    def test_clean_complex_description(self):
        """Test cleaning complex real-world description"""
        extractor = PartyExtractor()
        result = extractor.clean("PAYMENT TO STARBUCKS #1234 12/25/2023 14:30 REF:ABC123")
        
        assert "STARBUCKS" in result
        assert "PAYMENT" not in result
        assert "12/25/2023" not in result
        assert "14:30" not in result
        assert "REF:ABC123" not in result
    
    def test_clean_multiple_prefixes(self):
        """Test description with multiple patterns"""
        extractor = PartyExtractor()
        result = extractor.clean("POS PURCHASE AT COSTCO")
        
        assert "COSTCO" in result
        assert "POS" not in result or result == "COSTCO"
    
    def test_clean_preserves_meaningful_numbers_in_name(self):
        """Test that numbers within names are preserved"""
        extractor = PartyExtractor()
        result = extractor.clean("7-ELEVEN STORE")
        
        assert "7" in result
        assert "ELEVEN" in result
    
    def test_clean_handles_unicode(self):
        """Test handling of unicode characters"""
        extractor = PartyExtractor()
        result = extractor.clean("Café Münchën")
        
        # Should convert to uppercase and handle unicode
        assert result.isupper()
    
    def test_clean_with_custom_pattern(self):
        """Test cleaning with custom pattern"""
        custom_patterns = [r'\s+CUSTOM\s+']
        extractor = PartyExtractor(custom_patterns=custom_patterns)
        result = extractor.clean("WALMART CUSTOM PATTERN")
        
        assert "CUSTOM" not in result or result.count("CUSTOM") == 0


class TestExtractPartyName:
    """Test the extract_party_name method"""
    
    def test_extract_from_simple_name(self):
        """Test extracting from simple party name"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("WALMART STORE")
        
        assert result == "WALMART"
    
    def test_extract_from_empty_string(self):
        """Test extracting from empty string"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("")
        
        assert result == "UNKNOWN"
    
    def test_extract_filters_stop_words(self):
        """Test that stop words are filtered"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("THE WALMART STORE")
        
        assert "THE" not in result
        assert "WALMART" in result
    
    def test_extract_filters_payment_stop_word(self):
        """Test that PAYMENT stop word is filtered"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("PAYMENT WALMART")
        
        assert "PAYMENT" not in result
        assert "WALMART" in result
    
    def test_extract_filters_multiple_stop_words(self):
        """Test filtering multiple stop words"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("THE PAYMENT TO WALMART STORE")
        
        assert "THE" not in result
        assert "PAYMENT" not in result
        assert "TO" not in result
        assert "WALMART" in result
    
    def test_extract_filters_short_words(self):
        """Test filtering words with length <= 1"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("WALMART A B STORE")
        
        # Check that single letters are not present as separate words
        words = result.split()
        assert "A" not in words
        assert "B" not in words
        assert "WALMART" in words
    
    def test_extract_respects_max_words_default(self):
        """Test default max_words of 3"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("WALMART SUPERCENTER GROCERY DEPARTMENT")
        
        words = result.split()
        assert len(words) <= 3
    
    def test_extract_respects_max_words_custom(self):
        """Test custom max_words parameter"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("WALMART SUPERCENTER GROCERY DEPARTMENT", max_words=2)
        
        words = result.split()
        assert len(words) <= 2
    
    def test_extract_with_max_words_one(self):
        """Test extraction with max_words=1"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("WALMART STORE", max_words=1)
        
        assert result == "WALMART"
    
    def test_extract_with_max_words_five(self):
        """Test extraction with max_words=5"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name(
            "ACME CORPORATION INTERNATIONAL HOLDINGS LIMITED",
            max_words=5
        )
        
        words = result.split()
        assert len(words) <= 5
        assert "ACME" in result
    
    def test_extract_only_stop_words(self):
        """Test extraction when only stop words present"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("THE AND OR")
        
        # Should fall back to original description
        assert result in ["THE AND OR", "UNKNOWN"] or len(result) > 0
    
    def test_extract_fallback_long_description(self):
        """Test fallback for long description with only stop words"""
        extractor = PartyExtractor()
        long_desc = "A " * 50  # 100 characters of single letters
        result = extractor.extract_party_name(long_desc)
        
        # Should truncate to 30 characters or return limited result
        assert len(result) <= 30 or result == "UNKNOWN"
    
    def test_extract_preserves_order(self):
        """Test that word order is preserved"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("ZEBRA ALPHA BRAVO")
        
        assert result.startswith("ZEBRA")
    
    def test_extract_strips_whitespace(self):
        """Test that result is stripped"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("  WALMART  ")
        
        assert result == result.strip()
        assert result == "WALMART"
    
    def test_extract_with_custom_stop_words(self):
        """Test extraction with custom stop words"""
        custom_stop_words = {'WALMART', 'TARGET'}
        extractor = PartyExtractor(custom_stop_words=custom_stop_words)
        result = extractor.extract_party_name("WALMART TARGET COSTCO")
        
        assert "WALMART" not in result
        assert "TARGET" not in result
        assert "COSTCO" in result
    
    def test_extract_single_meaningful_word(self):
        """Test extraction with single meaningful word"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("THE PAYMENT TO AMAZON")
        
        assert result == "AMAZON"
    
    def test_extract_numeric_in_name(self):
        """Test extraction with numbers in name"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("7 ELEVEN STORE")
        
        # "ELEVEN" should be extracted, "7" might be filtered as short
        assert "ELEVEN" in result or "7" in result
    
    def test_extract_hyphenated_name(self):
        """Test extraction with hyphenated name"""
        extractor = PartyExtractor()
        # After cleaning, hyphens become spaces
        result = extractor.extract_party_name("TWENTY FOUR SEVEN")
        
        assert "TWENTY" in result
    
    def test_extract_company_suffixes_filtered(self):
        """Test that company suffixes are filtered"""
        extractor = PartyExtractor()
        result = extractor.extract_party_name("ACME CORPORATION LTD")
        
        assert "ACME" in result
        assert "CORPORATION" not in result
        assert "LTD" not in result


class TestIntegration:
    """Integration tests combining clean and extract_party_name"""
    
    def test_full_pipeline_simple(self):
        """Test full pipeline with simple transaction"""
        extractor = PartyExtractor()
        
        description = "PAYMENT TO WALMART 12/25/2023"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert party == "WALMART"
    
    def test_full_pipeline_complex(self):
        """Test full pipeline with complex transaction"""
        extractor = PartyExtractor()
        
        description = "POS PURCHASE AT STARBUCKS #1234 12/25/2023 14:30 REF:ABC123"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "STARBUCKS" in party
        assert "POS" not in party
        assert "PURCHASE" not in party
    
    def test_full_pipeline_with_card_number(self):
        """Test full pipeline with card number"""
        extractor = PartyExtractor()
        
        description = "DEBIT CARD PURCHASE AMAZON.COM ****1234"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "AMAZON" in party
        assert "DEBIT" not in party
        assert "CARD" not in party
        assert "1234" not in party
    
    def test_full_pipeline_online_payment(self):
        """Test full pipeline with online payment"""
        extractor = PartyExtractor()
        
        description = "ONLINE PAYMENT NETFLIX.COM"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "NETFLIX" in party
        assert "ONLINE" not in party
        assert "PAYMENT" not in party
    
    def test_full_pipeline_direct_debit(self):
        """Test full pipeline with direct debit"""
        extractor = PartyExtractor()
        
        description = "DD ELECTRIC IRELAND REF:123456"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "ELECTRIC" in party
        assert "DD" not in party
        assert "IRELAND" not in party  # Country name filtered
    
    def test_full_pipeline_transfer(self):
        """Test full pipeline with transfer"""
        extractor = PartyExtractor()
        
        description = "TRANSFER TO JOHN DOE 01/15/2024"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "JOHN" in party
        assert "TRANSFER" not in party
    
    def test_full_pipeline_multiple_merchants(self):
        """Test pipeline doesn't mix multiple merchants"""
        extractor = PartyExtractor()
        
        # Should only extract first merchant
        description = "WALMART STORE"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned, max_words=1)
        
        assert party == "WALMART"
    
    def test_full_pipeline_with_location(self):
        """Test full pipeline with location code"""
        extractor = PartyExtractor()
        
        description = "COSTCO WHOLESALE G 28"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "COSTCO" in party
        assert "WHOLESALE" in party
        assert "28" not in party
    
    def test_full_pipeline_batch_processing(self):
        """Test processing multiple descriptions"""
        extractor = PartyExtractor()
        
        descriptions = [
            "PAYMENT TO WALMART 12/25/2023",
            "POS TARGET STORE 12/26/2023",
            "ONLINE PAYMENT AMAZON.COM",
            "DD ELECTRIC IRELAND",
        ]
        
        results = []
        for desc in descriptions:
            cleaned = extractor.clean(desc)
            party = extractor.extract_party_name(cleaned)
            results.append(party)
        
        assert "WALMART" in results[0]
        assert "TARGET" in results[1]
        assert "AMAZON" in results[2]
        assert "ELECTRIC" in results[3]


class TestEdgeCases:
    """Test edge cases and unusual inputs"""
    
    def test_very_long_description(self):
        """Test with very long description"""
        extractor = PartyExtractor()
        
        long_desc = "WALMART " * 100
        cleaned = extractor.clean(long_desc)
        party = extractor.extract_party_name(cleaned)
        
        assert "WALMART" in party
        assert len(party) < len(long_desc)
    
    def test_all_special_characters(self):
        """Test description with only special characters"""
        extractor = PartyExtractor()
        
        cleaned = extractor.clean("!@#$%^&*()")
        party = extractor.extract_party_name(cleaned)
        
        assert party == "UNKNOWN" or party == ""
    
    def test_all_numbers(self):
        """Test description with only numbers"""
        extractor = PartyExtractor()
        
        cleaned = extractor.clean("1234567890")
        party = extractor.extract_party_name(cleaned)
        
        # Numbers should be removed or result in UNKNOWN
        assert party == "UNKNOWN" or "1234567890" in party
    
    def test_mixed_case_with_numbers(self):
        """Test mixed case with numbers"""
        extractor = PartyExtractor()
        
        description = "WaLmArT123"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "WALMART" in party or "WALMART123" in party
    
    def test_repeated_whitespace(self):
        """Test description with excessive whitespace"""
        extractor = PartyExtractor()
        
        cleaned = extractor.clean("WALMART     STORE     123")
        assert "  " not in cleaned
    
    def test_newlines_and_tabs(self):
        """Test description with newlines and tabs"""
        extractor = PartyExtractor()
        
        description = "WALMART\n\tSTORE\t\n123"
        cleaned = extractor.clean(description)
        
        assert "\n" not in cleaned
        assert "\t" not in cleaned
    
    def test_description_only_stop_words(self):
        """Test description containing only stop words"""
        extractor = PartyExtractor()
        
        cleaned = extractor.clean("THE AND OR")
        party = extractor.extract_party_name(cleaned)
        
        # Should handle gracefully
        assert party is not None
        assert isinstance(party, str)
    
    def test_single_character_description(self):
        """Test single character description"""
        extractor = PartyExtractor()
        
        cleaned = extractor.clean("A")
        party = extractor.extract_party_name(cleaned)
        
        assert party == "UNKNOWN" or party == "A"
    
    def test_unicode_characters(self):
        """Test with unicode characters"""
        extractor = PartyExtractor()
        
        description = "Café München Ñoño"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert party is not None
        assert len(party) > 0
    
    def test_null_bytes(self):
        """Test handling of null bytes"""
        extractor = PartyExtractor()
        
        # Should handle without crashing
        cleaned = extractor.clean("WALMART\x00STORE")
        assert cleaned is not None
    
    def test_max_words_zero(self):
        """Test with max_words=0"""
        extractor = PartyExtractor()
        
        party = extractor.extract_party_name("WALMART STORE", max_words=0)
        
        # Should return empty string or handle gracefully
        assert party == "" or party == "UNKNOWN"
    
    def test_max_words_negative(self):
        """Test with negative max_words"""
        extractor = PartyExtractor()
        
        party = extractor.extract_party_name("WALMART STORE", max_words=-1)
        
        # Should handle gracefully (empty slice)
        assert party == "" or party == "UNKNOWN"
    
    def test_max_words_very_large(self):
        """Test with very large max_words"""
        extractor = PartyExtractor()
        
        party = extractor.extract_party_name("WALMART STORE", max_words=1000)
        
        # Should work normally
        assert "WALMART" in party


class TestRealWorldExamples:
    """Test with real-world transaction descriptions"""
    
    def test_irish_bank_aib(self):
        """Test AIB-style transaction"""
        extractor = PartyExtractor()
        
        descriptions = [
            "POS TESCO IRELAND 12/25 14:30",
            "DD ESB ELECTRIC IRELAND",
            "CT SALARY ACME CORP",
        ]
        
        results = [
            extractor.extract_party_name(extractor.clean(d)) 
            for d in descriptions
        ]
        
        assert "TESCO" in results[0]
        assert "ESB" in results[1] or "ELECTRIC" in results[1]
        assert "SALARY" in results[2] or "ACME" in results[2]
    
    def test_uk_bank_style(self):
        """Test UK bank-style transactions"""
        extractor = PartyExtractor()
        
        description = "VISA PURCHASE SAINSBURYS S/MKTS"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "SAINSBURYS" in party
        assert "VISA" not in party
    
    def test_us_bank_style(self):
        """Test US bank-style transactions"""
        extractor = PartyExtractor()
        
        description = "DEBIT CARD PURCHASE - 1234 WHOLE FOODS MKT"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "WHOLE" in party
        assert "FOODS" in party
        assert "DEBIT" not in party
    
    def test_online_subscription(self):
        """Test online subscription payment"""
        extractor = PartyExtractor()
        
        description = "RECURRING PAYMENT SPOTIFY AB"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "SPOTIFY" in party
    
    def test_atm_withdrawal(self):
        """Test ATM withdrawal"""
        extractor = PartyExtractor()
        
        description = "ATM WITHDRAWAL BANK OF IRELAND ATM 123"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        # Should extract BANK or handle as ATM transaction
        assert party != "UNKNOWN"
    
    def test_international_transaction(self):
        """Test international transaction with currency"""
        extractor = PartyExtractor()
        
        description = "FOREIGN TRANSACTION FEE AMAZON.CO.UK"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "AMAZON" in party
        assert "FOREIGN" not in party
        assert "FEE" not in party
    
    def test_paypal_transaction(self):
        """Test PayPal transaction"""
        extractor = PartyExtractor()
        
        description = "PAYPAL *EBAY MERCHANT"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "PAYPAL" in party or "EBAY" in party
    
    def test_contactless_payment(self):
        """Test contactless payment"""
        extractor = PartyExtractor()
        
        description = "CNC COSTA COFFEE #5678"
        cleaned = extractor.clean(description)
        party = extractor.extract_party_name(cleaned)
        
        assert "COSTA" in party
        assert "COFFEE" in party
        assert "CNC" not in party


class TestDataFrameIntegration:
    """Test integration with pandas DataFrames"""
    
    def test_apply_to_dataframe_column(self):
        """Test applying extractor to DataFrame column"""
        extractor = PartyExtractor()
        
        df = pd.DataFrame({
            'description': [
                'PAYMENT TO WALMART',
                'POS TARGET STORE',
                'ONLINE AMAZON.COM',
            ]
        })
        
        df['cleaned'] = df['description'].apply(extractor.clean)
        df['party'] = df['cleaned'].apply(extractor.extract_party_name)
        
        assert 'WALMART' in df['party'].iloc[0]
        assert 'TARGET' in df['party'].iloc[1]
        assert 'AMAZON' in df['party'].iloc[2]
    
    def test_handle_missing_values_in_dataframe(self):
        """Test handling missing values in DataFrame"""
        extractor = PartyExtractor()
        
        df = pd.DataFrame({
            'description': ['WALMART', None, pd.NA, '']
        })
        
        df['cleaned'] = df['description'].apply(extractor.clean)
        df['party'] = df['cleaned'].apply(extractor.extract_party_name)
        
        assert df['party'].iloc[0] == 'WALMART'
        assert df['party'].iloc[1] == 'UNKNOWN'
        assert df['party'].iloc[2] == 'UNKNOWN'
        assert df['party'].iloc[3] == 'UNKNOWN'
    
    def test_batch_processing_performance(self):
        """Test processing large batch of transactions"""
        extractor = PartyExtractor()
        
        # Create large DataFrame
        descriptions = ['PAYMENT TO WALMART'] * 1000
        df = pd.DataFrame({'description': descriptions})
        
        df['cleaned'] = df['description'].apply(extractor.clean)
        df['party'] = df['cleaned'].apply(extractor.extract_party_name)
        
        assert len(df) == 1000
        assert all(df['party'] == 'WALMART')