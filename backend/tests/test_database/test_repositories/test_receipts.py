import pytest
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import numpy as np

from src.database.connection import ConnectionManager, DatabaseError, init as init_connection
from src.database.schema import initialize_schema
from src.database.repositories.receipts import ReceiptRepository
from src.models.receipt import Receipt


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path"""
    return tmp_path / "test.db"


@pytest.fixture
def connection_manager(temp_db_path):
    """Create and initialize connection manager"""
    manager = ConnectionManager(temp_db_path)
    init_connection(temp_db_path)  # Set as default manager
    initialize_schema(manager)
    return manager


@pytest.fixture
def repo(connection_manager):
    """Create a receipt repository"""
    return ReceiptRepository()


@pytest.fixture
def sample_receipt():
    """Create a sample receipt object"""
    return Receipt(
        original_filename=Path("receipt_001.pdf"),
        page_number=1,
        original_image=np.zeros((100, 100, 3), dtype=np.uint8),
        processed_images={"denoise": np.zeros((100, 100, 3), dtype=np.uint8)},
        extracted_text="WALMART\nTotal: $25.99",
        selected_method="denoise",
        confidence=3,
        vendor="WALMART",
        date=datetime(2024, 1, 15),
        amount=25.99,
        stored_filename="2024_01_15_receipt_001.pdf",
        file_path=Path("/data/receipts/2024_01_15_receipt_001.pdf")
    )


@pytest.fixture
def multiple_receipts():
    """Create multiple receipt objects for testing"""
    receipts = []
    
    vendors = ["WALMART", "TARGET", "COSTCO", "WALMART", "TARGET"]
    amounts = [25.99, 45.50, 123.45, 67.89, 34.21]
    confidences = [3, 2, 3, 1, 3]
    
    for i, (vendor, amount, confidence) in enumerate(zip(vendors, amounts, confidences)):
        receipt = Receipt(
            original_filename=Path(f"receipt_{i:03d}.pdf"),
            page_number=1,
            original_image=np.zeros((100, 100, 3), dtype=np.uint8),
            processed_images={},
            extracted_text=f"{vendor}\nTotal: ${amount}",
            selected_method="denoise",
            confidence=confidence,
            vendor=vendor,
            date=datetime(2024, 1, 15 + i),
            amount=amount,
            stored_filename=f"2024_01_{15+i:02d}_receipt_{i:03d}.pdf",
            file_path=Path(f"/data/receipts/2024_01_{15+i:02d}_receipt_{i:03d}.pdf")
        )
        receipts.append(receipt)
    
    return receipts


class TestSaveReceipt:
    """Test saving receipts"""
    
    def test_save_returns_id(self, repo, sample_receipt):
        """Test that save returns an ID"""
        receipt_id = repo.save(sample_receipt)
        assert isinstance(receipt_id, int)
        assert receipt_id > 0
    
    def test_save_stores_data(self, repo, sample_receipt):
        """Test that receipt data is stored correctly"""
        receipt_id = repo.save(sample_receipt)
        saved = repo.get_by_id(receipt_id)
        
        assert saved['original_filename'] == str(sample_receipt.original_filename)
        assert saved['stored_filename'] == sample_receipt.stored_filename
        assert saved['vendor'] == sample_receipt.vendor
        assert saved['amount'] == sample_receipt.amount
        assert saved['confidence'] == sample_receipt.confidence
    
    def test_save_with_date(self, repo, sample_receipt):
        """Test saving receipt with datetime"""
        receipt_id = repo.save(sample_receipt)
        saved = repo.get_by_id(receipt_id)
        
        assert isinstance(saved['date'], datetime)
        assert saved['date'].date() == sample_receipt.date.date()
    
    def test_save_without_date(self, repo, sample_receipt):
        """Test saving receipt without date"""
        sample_receipt.date = None
        receipt_id = repo.save(sample_receipt)
        saved = repo.get_by_id(receipt_id)
        
        assert saved['date'] is None
    
    def test_save_with_metadata(self, repo, sample_receipt):
        """Test that metadata is saved"""
        receipt_id = repo.save(sample_receipt)
        saved = repo.get_by_id(receipt_id)
        
        assert 'metadata' in saved
        assert isinstance(saved['metadata'], dict)
        assert saved['metadata']['selected_method'] == 'denoise'
        assert saved['metadata']['page_number'] == 1
    
    def test_save_duplicate_raises_error(self, repo, sample_receipt):
        """Test that saving duplicate raises DatabaseError"""
        repo.save(sample_receipt)
        
        with pytest.raises(DatabaseError) as exc_info:
            repo.save(sample_receipt)
        
        assert "already exists" in str(exc_info.value).lower()
    
    def test_save_with_invalid_amount(self, repo, sample_receipt):
        """Test saving receipt with invalid amount"""
        sample_receipt.amount = -10.00
        
        with pytest.raises(DatabaseError):
            repo.save(sample_receipt)
    
    def test_save_increments_id(self, repo, multiple_receipts):
        """Test that IDs are incremented"""
        ids = []
        for receipt in multiple_receipts:
            receipt_id = repo.save(receipt)
            ids.append(receipt_id)
        
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)
    
    def test_save_sets_timestamps(self, repo, sample_receipt):
        """Test that timestamps are set"""
        receipt_id = repo.save(sample_receipt)
        saved = repo.get_by_id(receipt_id)
        
        assert saved['created_at'] is not None
        assert saved['updated_at'] is not None
    
    def test_save_with_minimal_data(self, repo):
        """Test saving receipt with minimal data"""
        receipt = Receipt(
            original_filename=Path("test.pdf"),
            page_number=1,
            original_image=np.zeros((10, 10, 3), dtype=np.uint8),
            processed_images={},
            extracted_text=None,
            selected_method=None,
            confidence=0,
            vendor=None,
            amount=None,
            date=None,
            stored_filename="stored_test.pdf",
            file_path=Path("/data/stored_test.pdf")  # Provide a path
        )
        
        receipt_id = repo.save(receipt)
        assert receipt_id > 0


class TestGetReceipts:
    """Test retrieving receipts"""
    
    def test_get_all_empty_database(self, repo):
        """Test getting receipts from empty database"""
        receipts = repo.get_all()
        assert receipts == []
    
    def test_get_all_returns_all(self, repo, multiple_receipts):
        """Test getting all receipts"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        receipts = repo.get_all(limit=100)
        assert len(receipts) == len(multiple_receipts)
    
    def test_get_all_limit(self, repo, multiple_receipts):
        """Test limit parameter"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        receipts = repo.get_all(limit=3)
        assert len(receipts) == 3
    
    def test_get_all_offset(self, repo, multiple_receipts):
        """Test offset parameter"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        first_page = repo.get_all(limit=2, offset=0)
        second_page = repo.get_all(limit=2, offset=2)
        
        assert len(first_page) == 2
        assert len(second_page) == 2
        assert first_page[0]['id'] != second_page[0]['id']
    
    def test_get_all_ordered_by_created_desc(self, repo, multiple_receipts):
        """Test that receipts are ordered by creation date descending"""
        ids = []
        for receipt in multiple_receipts:
            receipt_id = repo.save(receipt)
            ids.append(receipt_id)
        
        receipts = repo.get_all()
        receipt_ids = [r['id'] for r in receipts]
        
        assert receipt_ids == list(reversed(ids))
    
    def test_get_all_filter_by_vendor(self, repo, multiple_receipts):
        """Test filtering by vendor"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        walmart_receipts = repo.get_all(vendor="WALMART")
        assert len(walmart_receipts) == 2
        assert all(r['vendor'] == "WALMART" for r in walmart_receipts)
    
    def test_get_all_filter_vendor_partial_match(self, repo, multiple_receipts):
        """Test vendor filter with partial match"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        receipts = repo.get_all(vendor="WAL")
        assert len(receipts) == 2
    
    def test_get_all_filter_by_min_confidence(self, repo, multiple_receipts):
        """Test filtering by minimum confidence"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        high_confidence = repo.get_all(min_confidence=3)
        assert len(high_confidence) == 3
        assert all(r['confidence'] >= 3 for r in high_confidence)
    
    def test_get_all_filter_by_date_range(self, repo, multiple_receipts):
        """Test filtering by date range"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        start = datetime(2024, 1, 16)
        end = datetime(2024, 1, 18)
        
        receipts = repo.get_all(start_date=start, end_date=end)
        assert len(receipts) == 3
        
        for receipt in receipts:
            assert start.date() <= receipt['date'].date() <= end.date()
    
    def test_get_all_combined_filters(self, repo, multiple_receipts):
        """Test multiple filters together"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        receipts = repo.get_all(
            vendor="WALMART",
            min_confidence=2,
            limit=10
        )
        
        assert len(receipts) <= 10
        assert all(r['vendor'] == "WALMART" for r in receipts)
        assert all(r['confidence'] >= 2 for r in receipts)
    
    def test_get_all_returns_dict(self, repo, sample_receipt):
        """Test that receipts are returned as dictionaries"""
        repo.save(sample_receipt)
        receipts = repo.get_all()
        
        assert isinstance(receipts, list)
        assert isinstance(receipts[0], dict)


class TestGetReceiptById:
    """Test retrieving single receipt"""
    
    def test_get_by_id_exists(self, repo, sample_receipt):
        """Test getting existing receipt"""
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert receipt is not None
        assert receipt['id'] == receipt_id
        assert receipt['vendor'] == sample_receipt.vendor
    
    def test_get_by_id_not_exists(self, repo):
        """Test getting non-existent receipt"""
        receipt = repo.get_by_id(999)
        assert receipt is None
    
    def test_get_by_id_returns_dict(self, repo, sample_receipt):
        """Test return type"""
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert isinstance(receipt, dict)
    
    def test_get_by_id_includes_metadata(self, repo, sample_receipt):
        """Test that metadata is included and parsed"""
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert 'metadata' in receipt
        assert isinstance(receipt['metadata'], dict)


class TestUpdateReceipt:
    """Test updating receipts"""
    
    def test_update_vendor(self, repo, sample_receipt):
        """Test updating vendor"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(receipt_id, vendor="TARGET")
        
        assert updated['vendor'] == "TARGET"
        assert updated['amount'] == sample_receipt.amount
    
    def test_update_amount(self, repo, sample_receipt):
        """Test updating amount"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(receipt_id, amount=99.99)
        
        assert updated['amount'] == 99.99
    
    def test_update_date(self, repo, sample_receipt):
        """Test updating date"""
        receipt_id = repo.save(sample_receipt)
        new_date = datetime(2024, 2, 1)
        
        updated = repo.update(receipt_id, date=new_date)
        
        assert updated['date'].date() == new_date.date()
    
    def test_update_confidence(self, repo, sample_receipt):
        """Test updating confidence"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(receipt_id, confidence=2)
        
        assert updated['confidence'] == 2
    
    def test_update_multiple_fields(self, repo, sample_receipt):
        """Test updating multiple fields"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(
            receipt_id,
            vendor="COSTCO",
            amount=150.00,
            confidence=3
        )
        
        assert updated['vendor'] == "COSTCO"
        assert updated['amount'] == 150.00
        assert updated['confidence'] == 3
    
    def test_update_no_changes(self, repo, sample_receipt):
        """Test update with no fields specified"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(receipt_id)
        
        assert updated is not None
        assert updated['id'] == receipt_id
    
    def test_update_not_exists(self, repo):
        """Test updating non-existent receipt"""
        updated = repo.update(999, vendor="TEST")
        assert updated is None
    
    def test_update_updates_timestamp(self, repo, sample_receipt):
        """Test that updated_at timestamp is updated"""
        receipt_id = repo.save(sample_receipt)
        original = repo.get_by_id(receipt_id)
        
        import time
        time.sleep(0.01)
        
        repo.update(receipt_id, vendor="UPDATED")
        updated = repo.get_by_id(receipt_id)
        
        assert updated['updated_at'] != original['updated_at']
    
    def test_update_with_none_value(self, repo, sample_receipt):
        """Test setting field to None"""
        receipt_id = repo.save(sample_receipt)
        
        updated = repo.update(receipt_id, vendor=None)
        
        assert updated['vendor'] is None


class TestDeleteReceipt:
    """Test deleting receipts"""
    
    def test_delete_exists(self, repo, sample_receipt):
        """Test deleting existing receipt"""
        receipt_id = repo.save(sample_receipt)
        
        deleted = repo.delete(receipt_id)
        
        assert deleted is True
        assert repo.get_by_id(receipt_id) is None
    
    def test_delete_not_exists(self, repo):
        """Test deleting non-existent receipt"""
        deleted = repo.delete(999)
        assert deleted is False
    
    def test_delete_removes_from_list(self, repo, multiple_receipts):
        """Test that deleted receipt is removed from lists"""
        ids = []
        for receipt in multiple_receipts:
            receipt_id = repo.save(receipt)
            ids.append(receipt_id)
        
        repo.delete(ids[2])
        
        receipts = repo.get_all()
        remaining_ids = [r['id'] for r in receipts]
        
        assert ids[2] not in remaining_ids
        assert len(receipts) == len(multiple_receipts) - 1


class TestGetReceiptStats:
    """Test receipt statistics"""
    
    def test_get_stats_empty_database(self, repo):
        """Test stats on empty database"""
        stats = repo.get_stats()
        
        assert stats['total_receipts'] == 0
        assert stats['total_amount'] is None
        assert stats['avg_amount'] is None
        assert stats['unique_vendors'] == 0
    
    def test_get_stats_with_receipts(self, repo, multiple_receipts):
        """Test stats with receipts"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        stats = repo.get_stats()
        
        assert stats['total_receipts'] == 5
        assert stats['total_amount'] == pytest.approx(297.04, 0.01)
        assert stats['avg_confidence'] > 0
        assert stats['unique_vendors'] == 3
    
    def test_get_stats_avg_amount(self, repo, multiple_receipts):
        """Test average amount calculation"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        stats = repo.get_stats()
        expected_avg = sum(r.amount for r in multiple_receipts) / len(multiple_receipts)
        
        assert stats['avg_amount'] == pytest.approx(expected_avg, 0.01)
    
    def test_get_stats_date_range(self, repo, multiple_receipts):
        """Test earliest and latest date"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        stats = repo.get_stats()
        
        assert stats['earliest_date'] is not None
        assert stats['latest_date'] is not None
    
    def test_get_stats_high_confidence_count(self, repo, multiple_receipts):
        """Test high confidence count"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        stats = repo.get_stats()
        
        assert stats['high_confidence_count'] == 3
    
    def test_get_stats_top_vendors(self, repo, multiple_receipts):
        """Test top vendors list"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        stats = repo.get_stats()
        
        assert 'top_vendors' in stats
        assert isinstance(stats['top_vendors'], list)
        assert len(stats['top_vendors']) > 0
        
        vendors = [v['vendor'] for v in stats['top_vendors']]
        assert 'WALMART' in vendors
        assert 'TARGET' in vendors
    
    def test_get_stats_top_vendors_limited(self, repo):
        """Test that top vendors is limited to 10"""
        for i in range(15):
            receipt = Receipt(
                original_filename=Path(f"receipt_{i}.pdf"),
                page_number=1,
                original_image=np.zeros((10, 10, 3), dtype=np.uint8),
                processed_images={},
                extracted_text=f"VENDOR_{i}\nTotal: $10.00",
                selected_method="test",
                confidence=3,
                vendor=f"VENDOR_{i}",
                date=datetime(2024, 1, 1),
                amount=10.00,
                stored_filename=f"stored_{i}.pdf",
                file_path=Path(f"/data/{i}.pdf")
            )
            repo.save(receipt)
        
        stats = repo.get_stats()
        
        assert len(stats['top_vendors']) <= 10


class TestRowToDict:
    """Test row to dictionary conversion"""
    
    def test_row_to_dict_with_metadata(self, repo, sample_receipt):
        """Test metadata JSON parsing"""
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert isinstance(receipt['metadata'], dict)
        assert 'selected_method' in receipt['metadata']
    
    def test_row_to_dict_with_invalid_metadata(self, repo, sample_receipt, connection_manager):
        """Test handling of invalid JSON in metadata"""
        receipt_id = repo.save(sample_receipt)
        
        # Corrupt the metadata
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE receipts SET metadata = ? WHERE id = ?",
                ("invalid json{", receipt_id)
            )
            conn.commit()
        
        receipt = repo.get_by_id(receipt_id)
        assert receipt['metadata'] == {}
    
    def test_row_to_dict_date_conversion(self, repo, sample_receipt):
        """Test date string conversion to datetime"""
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert isinstance(receipt['date'], datetime)
    
    def test_row_to_dict_with_none_date(self, repo, sample_receipt):
        """Test handling None date"""
        sample_receipt.date = None
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert receipt['date'] is None


class TestEdgeCases:
    """Test edge cases"""
    
    def test_empty_vendor_string(self, repo, sample_receipt):
        """Test saving receipt with empty vendor string"""
        sample_receipt.vendor = ""
        receipt_id = repo.save(sample_receipt)
        
        receipt = repo.get_by_id(receipt_id)
        assert receipt['vendor'] == ""
    
    def test_very_long_vendor_name(self, repo, sample_receipt):
        """Test with very long vendor name"""
        sample_receipt.vendor = "A" * 1000
        receipt_id = repo.save(sample_receipt)
        
        receipt = repo.get_by_id(receipt_id)
        assert len(receipt['vendor']) == 1000
    
    def test_zero_amount(self, repo, sample_receipt):
        """Test with zero amount"""
        sample_receipt.amount = 0.0
        
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert receipt['amount'] == 0.0
    
    def test_negative_amount(self, repo, sample_receipt):
        """Test with negative amount - should fail"""
        sample_receipt.amount = -10.00
        
        with pytest.raises(DatabaseError):
            repo.save(sample_receipt)
    
    def test_very_large_amount(self, repo, sample_receipt):
        """Test with very large amount"""
        sample_receipt.amount = 999999.99
        receipt_id = repo.save(sample_receipt)
        
        receipt = repo.get_by_id(receipt_id)
        assert receipt['amount'] == 999999.99
    
    def test_special_characters_in_filename(self, repo, sample_receipt):
        """Test with special characters in filename"""
        sample_receipt.original_filename = Path("receipt's & file (2024).pdf")
        sample_receipt.stored_filename = "stored_receipt's_&_file_(2024).pdf"
        
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        
        assert receipt['original_filename'] == str(sample_receipt.original_filename)
    
    def test_unicode_in_vendor_name(self, repo, sample_receipt):
        """Test with unicode characters in vendor"""
        sample_receipt.vendor = "Café Müller"
        receipt_id = repo.save(sample_receipt)
        
        receipt = repo.get_by_id(receipt_id)
        assert receipt['vendor'] == "Café Müller"
    
    def test_very_long_text_field(self, repo, sample_receipt):
        """Test with very long extracted text"""
        sample_receipt.extracted_text = "text " * 10000
        receipt_id = repo.save(sample_receipt)
        
        receipt = repo.get_by_id(receipt_id)
        assert len(receipt['raw_text']) > 40000


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.integration
    def test_full_receipt_lifecycle(self, repo, sample_receipt):
        """Test complete CRUD cycle"""
        # Create
        receipt_id = repo.save(sample_receipt)
        assert receipt_id > 0
        
        # Read
        receipt = repo.get_by_id(receipt_id)
        assert receipt['vendor'] == sample_receipt.vendor
        
        # Update
        updated = repo.update(receipt_id, vendor="UPDATED VENDOR")
        assert updated['vendor'] == "UPDATED VENDOR"
        
        # Delete
        deleted = repo.delete(receipt_id)
        assert deleted is True
        
        # Verify deletion
        receipt = repo.get_by_id(receipt_id)
        assert receipt is None
    
    @pytest.mark.integration
    def test_complex_query_scenario(self, repo, multiple_receipts, tmp_path):
        """Test complex querying scenario"""
        for receipt in multiple_receipts:
            repo.save(receipt)
        
        receipts = repo.get_all(
            vendor="WALMART",
            min_confidence=2
        )
        
        assert len(receipts) > 0
        assert all(r['vendor'] == "WALMART" for r in receipts)
        assert all(r['confidence'] >= 2 for r in receipts)
        
        stats = repo.get_stats()
        assert stats['total_receipts'] == len(multiple_receipts)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])