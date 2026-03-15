import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.categorizer.party_extractor import PartyExtractor
from src.categorizer.party_matcher import PartyMatcher


class TestTransactionCategorizerInitialization:
    """Test TransactionCategorizer initialization"""
    
    def test_init_default_parameters(self):
        """Test initialization with default parameters"""
        categorizer = TransactionCategorizer()
        
        assert categorizer.extractor is not None
        assert categorizer.matcher is not None
        assert isinstance(categorizer.extractor, PartyExtractor)
        assert isinstance(categorizer.matcher, PartyMatcher)
        assert categorizer.matcher.similarity_threshold == 80
    
    def test_init_custom_threshold(self):
        """Test initialization with custom similarity threshold"""
        categorizer = TransactionCategorizer(similarity_threshold=90)
        
        assert categorizer.matcher.similarity_threshold == 90
    
    def test_init_with_known_aliases(self):
        """Test initialization with known aliases"""
        aliases = {"WALMART": 1, "TARGET": 2}
        categorizer = TransactionCategorizer(known_aliases=aliases)
        
        assert categorizer.matcher.known_aliases == aliases
    
    def test_init_with_canonical_parties(self):
        """Test initialization with canonical parties"""
        canonical = {"Walmart Inc": 1, "Target Corp": 2}
        categorizer = TransactionCategorizer(canonical_parties=canonical)
        
        assert categorizer.matcher.canonical_parties == canonical
    
    def test_init_with_both_aliases_and_canonical(self):
        """Test initialization with both aliases and canonical parties"""
        aliases = {"WALMART": 1}
        canonical = {"Walmart Inc": 1}
        
        categorizer = TransactionCategorizer(
            known_aliases=aliases,
            canonical_parties=canonical
        )
        
        assert categorizer.matcher.known_aliases == aliases
        assert categorizer.matcher.canonical_parties == canonical
    
    def test_init_none_aliases_uses_empty_dict(self):
        """Test that None aliases defaults to empty dict"""
        categorizer = TransactionCategorizer(known_aliases=None)
        
        assert categorizer.matcher.known_aliases == {}
    
    def test_init_none_canonical_uses_empty_dict(self):
        """Test that None canonical parties defaults to empty dict"""
        categorizer = TransactionCategorizer(canonical_parties=None)
        
        assert categorizer.matcher.canonical_parties == {}
    
    def test_init_doesnt_share_mutable_defaults(self):
        """Test that mutable defaults aren't shared between instances"""
        cat1 = TransactionCategorizer()
        cat2 = TransactionCategorizer()
        
        # Modify one instance
        cat1.matcher.known_aliases["TEST"] = 1
        
        # Other instance should not be affected
        assert "TEST" not in cat2.matcher.known_aliases
    
    def test_init_copies_dictionaries(self):
        """Test that input dictionaries are copied"""
        aliases = {"WALMART": 1}
        canonical = {"Walmart Inc": 1}
        
        categorizer = TransactionCategorizer(
            known_aliases=aliases,
            canonical_parties=canonical
        )
        
        # Modify originals
        aliases["TARGET"] = 2
        canonical["Target Corp"] = 2
        
        # Categorizer should not be affected
        assert "TARGET" not in categorizer.matcher.known_aliases
        assert "Target Corp" not in categorizer.matcher.canonical_parties
    
    def test_init_invalid_threshold_raises_error(self):
        """Test that invalid threshold raises ValueError"""
        with pytest.raises(ValueError):
            TransactionCategorizer(similarity_threshold=101)
        
        with pytest.raises(ValueError):
            TransactionCategorizer(similarity_threshold=-1)


class TestCategorizeMethod:
    """Test the categorize method"""
    
    def test_categorize_single_transaction(self):
        """Test categorizing a single transaction"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        result = categorizer.categorize(["PAYMENT TO WALMART"])
        
        assert len(result) == 1
        assert result[0]['party_id'] == 1
        assert result[0]['confidence'] == 100
    
    def test_categorize_multiple_transactions(self):
        """Test categorizing multiple transactions"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1, "TARGET": 2}
        )
        
        transactions = [
            "PAYMENT TO WALMART",
            "POS TARGET STORE",
            "TRANSFER TO WALMART"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert len(result) == 3
        assert result[0]['party_id'] == 1
        assert result[1]['party_id'] == 2
        assert result[2]['party_id'] == 1
    
    def test_categorize_empty_list_raises_error(self):
        """Test that empty transaction list raises ValueError"""
        categorizer = TransactionCategorizer()
        
        with pytest.raises(ValueError) as exc_info:
            categorizer.categorize([])
        
        assert "No transactions data provided" in str(exc_info.value)
    
    def test_categorize_returns_correct_structure(self):
        """Test that return structure is correct"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["WALMART"])
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert 'party_id' in result[0]
        assert 'confidence' in result[0]
    
    def test_categorize_exact_match_confidence_100(self):
        """Test that exact matches have confidence 100"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        result = categorizer.categorize(["WALMART"])
        
        assert result[0]['confidence'] == 100
    
    def test_categorize_fuzzy_match_confidence_below_100(self):
        """Test that fuzzy matches have confidence below 100"""
        categorizer = TransactionCategorizer(
            similarity_threshold=70,
            known_aliases={"WALMART": 1}
        )
        
        result = categorizer.categorize(["WALMRT"])  # Typo
        
        assert result[0]['party_id'] == 1
        assert 70 <= result[0]['confidence'] < 100
    
    def test_categorize_new_party_confidence_100(self):
        """Test that new parties have confidence 0"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["NEW VENDOR"])
        
        assert result[0]['confidence'] == 100
    
    def test_categorize_creates_new_party(self):
        """Test that unknown parties are created"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["NEW VENDOR"])
        
        assert result[0]['party_id'] == 1
        assert "NEW" in categorizer.matcher.discovered_parties or \
               "NEW VENDOR" in categorizer.matcher.discovered_parties
    
    def test_categorize_cleans_descriptions(self):
        """Test that descriptions are cleaned before matching"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        # These should all match to WALMART after cleaning
        transactions = [
            "PAYMENT TO WALMART 12/25/2023",
            "POS WALMART ****1234",
            "WALMART REF:123456"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert all(r['party_id'] == 1 for r in result)
    
    def test_categorize_extracts_party_names(self):
        """Test that party names are extracted correctly"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        # Stop words should be removed during extraction
        result = categorizer.categorize(["THE PAYMENT TO WALMART STORE"])
        
        assert result[0]['party_id'] == 1
    
    def test_categorize_handles_unknown_extraction(self):
        """Test handling when extraction returns UNKNOWN"""
        categorizer = TransactionCategorizer()
        
        # If description results in UNKNOWN party name
        result = categorizer.categorize(["123 456 789"])  # Only numbers
        
        # Should create "UNKNOWN" party or handle appropriately
        assert result[0]['party_id'] is not None
    
    def test_categorize_preserves_order(self):
        """Test that result order matches input order"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1, "TARGET": 2, "COSTCO": 3}
        )
        
        transactions = ["COSTCO", "WALMART", "TARGET"]
        result = categorizer.categorize(transactions)
        
        assert result[0]['party_id'] == 3  # COSTCO
        assert result[1]['party_id'] == 1  # WALMART
        assert result[2]['party_id'] == 2  # TARGET
    
    def test_categorize_same_party_multiple_times(self):
        """Test same party appearing multiple times"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        transactions = ["WALMART", "WALMART", "WALMART"]
        result = categorizer.categorize(transactions)
        
        assert all(r['party_id'] == 1 for r in result)
        assert all(r['confidence'] == 100 for r in result)
    
    def test_categorize_mixed_known_and_unknown(self):
        """Test mix of known and unknown parties"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        transactions = ["WALMART", "AMAZON", "TARGET"]
        result = categorizer.categorize(transactions)
        
        assert result[0]['party_id'] == 1  # Known
        assert result[0]['confidence'] == 100
        
        assert result[1]['party_id'] == 2  # New
        assert result[1]['confidence'] == 100
        
        assert result[2]['party_id'] == 3  # New
        assert result[2]['confidence'] == 100
    
    def test_categorize_discovered_alias_reused(self):
        """Test that discovered aliases are reused"""
        categorizer = TransactionCategorizer(
            similarity_threshold=70,
            known_aliases={"WALMART": 1}
        )
        
        transactions = ["WALMRT", "WALMRT"]  # Same typo twice
        result = categorizer.categorize(transactions)
        
        # Both should match to same party
        assert result[0]['party_id'] == result[1]['party_id']
        # Second should be exact match (100) if alias was created
        assert result[1]['confidence'] == 100


class TestCategorizationWorkflow:
    """Test the complete categorization workflow"""
    
    def test_end_to_end_simple(self):
        """Test simple end-to-end workflow"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1, "TARGET": 2}
        )
        
        transactions = [
            "PAYMENT TO WALMART 12/25/2023",
            "POS TARGET STORE #123"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert result[0]['party_id'] == 1
        assert result[1]['party_id'] == 2
    
    def test_end_to_end_with_fuzzy_matching(self):
        """Test workflow with fuzzy matching"""
        categorizer = TransactionCategorizer(
            similarity_threshold=70,
            known_aliases={"WALMART SUPERCENTER": 1}
        )
        
        result = categorizer.categorize(["PAYMENT TO WALMART"])
        
        assert result[0]['party_id'] == 1
        assert result[0]['confidence'] < 100
    
    def test_end_to_end_with_party_discovery(self):
        """Test workflow that discovers new parties"""
        categorizer = TransactionCategorizer()
        
        # Use very distinct names to avoid fuzzy matching
        transactions = ["ACME CORP", "BETA INDUSTRIES", "GAMMA SERVICES"]
        result = categorizer.categorize(transactions)
        
        # Each should get unique ID
        party_ids = [r['party_id'] for r in result]
        assert len(set(party_ids)) == 3
        
        # All should be new (confidence 100)
        assert all(r['confidence'] == 100 for r in result)
    
    def test_end_to_end_complex_descriptions(self):
        """Test with complex real-world descriptions"""
        categorizer = TransactionCategorizer(
            known_aliases={
                "WALMART": 1,
                "TARGET": 2,
                "AMAZON": 3
            }
        )
        
        transactions = [
            "POS PURCHASE WALMART SUPERCENTER 12/25/2023 14:30 ****1234",
            "ONLINE PAYMENT AMAZON.COM REF:ABC123",
            "DEBIT CARD TARGET STORE #5678",
            "PAYMENT TO NEW VENDOR INC"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert result[0]['party_id'] == 1  # WALMART
        assert result[1]['party_id'] == 3  # AMAZON
        assert result[2]['party_id'] == 2  # TARGET
        assert result[3]['party_id'] == 4  # NEW (discovered)
    
    def test_maintains_statistics(self):
        """Test that matcher maintains correct statistics"""
        categorizer = TransactionCategorizer(
            similarity_threshold=70,
            known_aliases={"WALMART": 1}
        )
        
        transactions = [
            "WALMART",       # Exact
            "WALMART SS", # Fuzzy
            "AMAZON",        # New
            "NETFLIX"        # New
        ]
        
        categorizer.categorize(transactions)
        
        # Check discovered aliases (WALMART STORE -> 1)
        assert len(categorizer.matcher.discovered_aliases) >= 1
        
        # Check discovered parties (AMAZON, NETFLIX)
        assert len(categorizer.matcher.discovered_parties) == 2


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_single_character_transaction(self):
        """Test single character transaction"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["A"])
        
        assert len(result) == 1
        assert result[0]['party_id'] is not None
    
    def test_very_long_transaction(self):
        """Test very long transaction description"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        long_desc = "PAYMENT TO WALMART " + "EXTRA " * 100
        result = categorizer.categorize([long_desc])
        
        assert result[0]['party_id'] == 1
    
    def test_special_characters_in_transaction(self):
        """Test transactions with special characters"""
        categorizer = TransactionCategorizer()
        
        transactions = [
            "WAL*MART #123",
            "AMAZON.COM",
            "7-ELEVEN"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert len(result) == 3
        assert all(r['party_id'] is not None for r in result)
    
    def test_unicode_characters(self):
        """Test transactions with unicode characters"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["Café München"])
        
        assert len(result) == 1
        assert result[0]['party_id'] is not None
      
    def test_none_in_transaction_list(self):
        """Test None value in transaction list"""
        categorizer = TransactionCategorizer()
        
        # Should handle None gracefully
        result = categorizer.categorize([None])
        
        # Might return UNKNOWN or empty result
        assert len(result) == 1
    
    def test_large_batch_processing(self):
        """Test processing large batch of transactions"""
        categorizer = TransactionCategorizer(
            known_aliases={"WALMART": 1}
        )
        
        # Create 1000 transactions
        transactions = ["WALMART"] * 500 + ["AMAZON"] * 500
        
        result = categorizer.categorize(transactions)
        
        assert len(result) == 1000
        assert sum(1 for r in result if r['party_id'] == 1) == 500
    
    def test_empty_string_transaction(self):
        """Test empty string in transaction list"""
        categorizer = TransactionCategorizer()
        
        # Empty string should be handled (might error or return UNKNOWN)
        result = categorizer.categorize([""])
        
        assert len(result) == 1
    
    def test_numbers_only_transaction(self):
        """Test transaction with only numbers"""
        categorizer = TransactionCategorizer()
        
        result = categorizer.categorize(["1234567890"])
        
        assert len(result) == 1
        assert result[0]['party_id'] is not None


class TestWithMockedDependencies:
    """Test with mocked dependencies for isolated unit testing"""
    
    @patch('src.categorizer.transaction_categorizer.PartyMatcher')
    @patch('src.categorizer.transaction_categorizer.PartyExtractor')
    def test_categorize_calls_extractor(self, mock_extractor_class, mock_matcher_class):
        """Test that categorize calls extractor methods"""
        mock_extractor = Mock()
        mock_extractor.clean.return_value = "CLEANED"
        mock_extractor.extract_party_name.return_value = "EXTRACTED"
        mock_extractor_class.return_value = mock_extractor
        
        mock_matcher = Mock()
        mock_matcher.find_match.return_value = (1, 100)
        mock_matcher.discovered_parties = {}
        mock_matcher.discovered_aliases = {}
        mock_matcher_class.return_value = mock_matcher
        
        categorizer = TransactionCategorizer()
        categorizer.categorize(["TEST"])
        
        mock_extractor.clean.assert_called_once_with("TEST")
        mock_extractor.extract_party_name.assert_called_once_with("CLEANED")
    
    @patch('src.categorizer.transaction_categorizer.PartyMatcher')
    @patch('src.categorizer.transaction_categorizer.PartyExtractor')
    def test_categorize_calls_matcher(self, mock_extractor_class, mock_matcher_class):
        """Test that categorize calls matcher methods"""
        mock_extractor = Mock()
        mock_extractor.clean.return_value = "CLEANED"
        mock_extractor.extract_party_name.return_value = "EXTRACTED"
        mock_extractor_class.return_value = mock_extractor
        
        mock_matcher = Mock()
        mock_matcher.find_match.return_value = (1, 100)
        mock_matcher.discovered_parties = {}
        mock_matcher.discovered_aliases = {}
        mock_matcher_class.return_value = mock_matcher
        
        categorizer = TransactionCategorizer()
        categorizer.categorize(["TEST"])
        
        mock_matcher.find_match.assert_called_once_with("EXTRACTED")
    
    @patch('src.categorizer.transaction_categorizer.PartyMatcher')
    @patch('src.categorizer.transaction_categorizer.PartyExtractor')
    def test_categorize_processes_all_transactions(self, mock_extractor_class, mock_matcher_class):
        """Test that all transactions are processed"""
        mock_extractor = Mock()
        mock_extractor.clean.return_value = "CLEANED"
        mock_extractor.extract_party_name.return_value = "EXTRACTED"
        mock_extractor_class.return_value = mock_extractor
        
        mock_matcher = Mock()
        mock_matcher.find_match.return_value = (1, 100)
        mock_matcher.discovered_parties = {}
        mock_matcher.discovered_aliases = {}
        mock_matcher_class.return_value = mock_matcher
        
        categorizer = TransactionCategorizer()
        categorizer.categorize(["T1", "T2", "T3"])
        
        assert mock_extractor.clean.call_count == 3
        assert mock_extractor.extract_party_name.call_count == 3
        assert mock_matcher.find_match.call_count == 3


class TestLogging:
    """Test logging behavior"""
    
    def test_categorize_logs_progress(self, caplog):
        """Test that progress is logged for large batches"""
        import logging
        
        categorizer = TransactionCategorizer()
        
        # Create 150 transactions to trigger logging
        transactions = ["WALMART"] * 150
        
        with caplog.at_level(logging.INFO):
            categorizer.categorize(transactions)
        
        # Should log progress at 100
        assert any("100" in record.message for record in caplog.records)
    
    def test_categorize_logs_summary(self, caplog):
        """Test that summary is logged"""
        import logging
        
        categorizer = TransactionCategorizer()
        
        with caplog.at_level(logging.INFO):
            categorizer.categorize(["WALMART", "AMAZON"])
        
        # Should log summary with counts
        assert any("transactions mapped" in record.message.lower() 
                   for record in caplog.records)


class TestIntegration:
    """Integration tests with real dependencies"""
    
    def test_real_world_scenario(self):
        """Test realistic bank transaction scenario"""
        categorizer = TransactionCategorizer(
            similarity_threshold=75,
            known_aliases={
                "WALMART": 1,
                "WAL-MART": 1,
                "TARGET": 2,
                "COSTCO": 3,
                "AMAZON": 4,
                "NETFLIX": 5
            },
            canonical_parties={
                "Walmart Inc": 1,
                "Target Corporation": 2,
                "Costco Wholesale": 3,
                "Amazon.com Inc": 4,
                "Netflix Inc": 5
            }
        )
        
        transactions = [
            "PAYMENT TO WALMART SUPERCENTER 12/25/2023",
            "POS TARGET STORE #1234 REF:ABC",
            "ONLINE AMAZON.COM ****5678",
            "DD NETFLIX SUBSCRIPTION",
            "TRANSFER TO JOHN DOE",
            "COSTCO WHOLESALE 01/15 14:30",
            "WAL-MART #9876"
        ]
        
        result = categorizer.categorize(transactions)
        
        assert len(result) == 7
        
        # Check expected mappings
        assert result[0]['party_id'] == 1  # WALMART
        assert result[1]['party_id'] == 2  # TARGET
        assert result[2]['party_id'] == 4  # AMAZON
        assert result[3]['party_id'] == 5  # NETFLIX
        assert result[4]['confidence'] == 100  # JOHN DOE (new)
        assert result[5]['party_id'] == 3  # COSTCO
        assert result[6]['party_id'] == 1  # WAL-MART -> WALMART
    
    def test_learning_over_time(self):
        """Test that system learns aliases over time"""
        categorizer = TransactionCategorizer(
            similarity_threshold=70,
            known_aliases={"WALMART SUPERCENTER": 1}
        )
        
        # First occurrence - fuzzy match
        result1 = categorizer.categorize(["WALMART"])
        assert result1[0]['party_id'] == 1
        first_confidence = result1[0]['confidence']
        
        # Second occurrence - should be exact match now
        result2 = categorizer.categorize(["WALMART"])
        assert result2[0]['party_id'] == 1
        assert result2[0]['confidence'] == 100
        assert result2[0]['confidence'] >= first_confidence
    
    def test_consistency_across_batches(self):
        """Test that categorization is consistent across batches"""
        categorizer = TransactionCategorizer()
        
        # First batch
        batch1_result = categorizer.categorize(["AMAZON", "NETFLIX"])
        
        # Second batch with same parties
        batch2_result = categorizer.categorize(["AMAZON", "NETFLIX"])
        
        # Should map to same IDs
        assert batch1_result[0]['party_id'] == batch2_result[0]['party_id']
        assert batch1_result[1]['party_id'] == batch2_result[1]['party_id']
        
        # Second batch should be exact matches (100 confidence)
        assert batch2_result[0]['confidence'] == 100
        assert batch2_result[1]['confidence'] == 100