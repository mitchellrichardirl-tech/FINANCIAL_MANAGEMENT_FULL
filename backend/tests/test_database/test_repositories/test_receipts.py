"""
ReceiptRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched tests are the DatabaseError-wrapping checks.
"""
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from src.database.errors import DatabaseError
from src.database.repositories.receipts import ReceiptRepository
from src.models.receipt import Receipt


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield ReceiptRepository()


def make_receipt(**overrides) -> Receipt:
    """Build a Receipt model instance with sensible defaults."""
    defaults = dict(
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
        file_path=Path("/data/receipts/2024_01_15_receipt_001.pdf"),
    )
    defaults.update(overrides)
    return Receipt(**defaults)


@pytest.fixture
def sample_receipt():
    return make_receipt()


@pytest.fixture
def multiple_receipts():
    """Five receipts: 2x WALMART, 2x TARGET, 1x COSTCO, dated Jan 15-19."""
    vendors = ["WALMART", "TARGET", "COSTCO", "WALMART", "TARGET"]
    amounts = [25.99, 45.50, 123.45, 67.89, 34.21]
    confidences = [3, 2, 3, 1, 3]

    return [
        make_receipt(
            original_filename=Path(f"receipt_{i:03d}.pdf"),
            processed_images={},
            extracted_text=f"{vendor}\nTotal: ${amount}",
            confidence=confidence,
            vendor=vendor,
            date=datetime(2024, 1, 15 + i),
            amount=amount,
            stored_filename=f"2024_01_{15 + i:02d}_receipt_{i:03d}.pdf",
            file_path=Path(f"/data/receipts/2024_01_{15 + i:02d}_receipt_{i:03d}.pdf"),
        )
        for i, (vendor, amount, confidence) in enumerate(
            zip(vendors, amounts, confidences)
        )
    ]


@pytest.fixture
def saved_receipts(repo, multiple_receipts):
    """The five receipts above, persisted. Returns their ids in creation order."""
    return [repo.save(r) for r in multiple_receipts]


# --------------------------------------------------------------------------- #
# save
# --------------------------------------------------------------------------- #
class TestSaveReceipt:

    def test_returns_id_of_persisted_row(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert isinstance(receipt_id, int) and receipt_id > 0

        saved = repo.get_by_id(receipt_id)
        assert saved['original_filename'] == str(sample_receipt.original_filename)
        assert saved['stored_filename'] == sample_receipt.stored_filename
        assert saved['file_path'] == str(sample_receipt.file_path)
        assert saved['vendor'] == sample_receipt.vendor
        assert saved['amount'] == sample_receipt.amount
        assert saved['confidence'] == sample_receipt.confidence
        assert saved['raw_text'] == sample_receipt.extracted_text

    def test_date_round_trips_as_datetime(self, repo, sample_receipt):
        saved = repo.get_by_id(repo.save(sample_receipt))
        assert isinstance(saved['date'], datetime)
        assert saved['date'].date() == sample_receipt.date.date()

    def test_date_may_be_null(self, repo, sample_receipt):
        sample_receipt.date = None
        assert repo.get_by_id(repo.save(sample_receipt))['date'] is None

    def test_metadata_captures_method_and_page(self, repo, sample_receipt):
        saved = repo.get_by_id(repo.save(sample_receipt))
        assert saved['metadata'] == {'selected_method': 'denoise', 'page_number': 1}

    def test_defaults_to_pending_and_unlinked(self, repo, sample_receipt):
        saved = repo.get_by_id(repo.save(sample_receipt))
        assert saved['status'] == 'pending'
        assert saved['linked_transaction_id'] is None

    def test_timestamps_are_set(self, repo, sample_receipt):
        saved = repo.get_by_id(repo.save(sample_receipt))
        assert saved['created_at'] is not None
        assert saved['updated_at'] is not None

    def test_duplicate_stored_filename_rejected(self, repo, sample_receipt):
        repo.save(sample_receipt)
        with pytest.raises(DatabaseError) as exc:
            repo.save(sample_receipt)
        assert "already exists" in str(exc.value).lower()

    def test_negative_amount_rejected(self, repo, sample_receipt):
        sample_receipt.amount = -10.00
        with pytest.raises(DatabaseError):
            repo.save(sample_receipt)

    def test_confidence_out_of_range_rejected(self, repo, sample_receipt):
        sample_receipt.confidence = 9
        with pytest.raises(DatabaseError):
            repo.save(sample_receipt)

    def test_ids_increment(self, repo, multiple_receipts):
        ids = [repo.save(r) for r in multiple_receipts]
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)

    def test_minimal_receipt(self, repo):
        receipt_id = repo.save(make_receipt(
            original_filename=Path("test.pdf"),
            processed_images={},
            extracted_text=None,
            selected_method=None,
            confidence=0,
            vendor=None,
            amount=None,
            date=None,
            stored_filename="stored_test.pdf",
            file_path=Path("/data/stored_test.pdf"),
        ))
        saved = repo.get_by_id(receipt_id)
        assert (saved['vendor'], saved['amount'], saved['date']) == (None, None, None)


# --------------------------------------------------------------------------- #
# get_all
# --------------------------------------------------------------------------- #
class TestGetAll:

    def test_empty_database(self, repo):
        assert repo.get_all() == []

    def test_returns_all(self, repo, saved_receipts):
        assert len(repo.get_all(limit=100)) == len(saved_receipts)

    def test_limit(self, repo, saved_receipts):
        assert len(repo.get_all(limit=3)) == 3

    def test_offset(self, repo, saved_receipts):
        page1 = repo.get_all(limit=2, offset=0)
        page2 = repo.get_all(limit=2, offset=2)
        assert len(page1) == len(page2) == 2
        assert not {r['id'] for r in page1} & {r['id'] for r in page2}

    def test_ordered_by_created_descending(self, repo, saved_receipts):
        assert [r['id'] for r in repo.get_all()] == list(reversed(saved_receipts))

    def test_filter_by_vendor(self, repo, saved_receipts):
        found = repo.get_all(vendor="WALMART")
        assert len(found) == 2
        assert all(r['vendor'] == "WALMART" for r in found)

    def test_filter_by_vendor_substring(self, repo, saved_receipts):
        assert len(repo.get_all(vendor="WAL")) == 2

    def test_filter_by_min_confidence(self, repo, saved_receipts):
        found = repo.get_all(min_confidence=3)
        assert len(found) == 3
        assert all(r['confidence'] >= 3 for r in found)

    def test_filter_by_date_range(self, repo, saved_receipts):
        start, end = datetime(2024, 1, 16), datetime(2024, 1, 18)
        found = repo.get_all(start_date=start, end_date=end)
        assert len(found) == 3
        assert all(start.date() <= r['date'].date() <= end.date() for r in found)

    def test_filters_are_anded(self, repo, saved_receipts):
        found = repo.get_all(vendor="WALMART", min_confidence=2)
        assert [r['vendor'] for r in found] == ["WALMART"]

    def test_no_match_returns_empty(self, repo, saved_receipts):
        assert repo.get_all(vendor="NOPE") == []


# --------------------------------------------------------------------------- #
# get_by_id
# --------------------------------------------------------------------------- #
class TestGetById:

    def test_found(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        receipt = repo.get_by_id(receipt_id)
        assert isinstance(receipt, dict)
        assert receipt['id'] == receipt_id
        assert receipt['vendor'] == sample_receipt.vendor

    def test_missing_returns_none(self, repo):
        assert repo.get_by_id(999) is None

    def test_includes_link_columns(self, repo, sample_receipt, app_with_db, make_transaction):
        from src.services.receipt_links import ReceiptLinkService

        receipt_id = repo.save(sample_receipt)
        txn_id = make_transaction()
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, txn_id)

        receipt = repo.get_by_id(receipt_id)
        assert receipt['linked_transaction_id'] == txn_id
        assert receipt['linked_at'] is not None


# --------------------------------------------------------------------------- #
# list / count_by_status
# --------------------------------------------------------------------------- #
class TestList:

    def test_returns_rows_and_total(self, repo, saved_receipts):
        rows, total = repo.list(limit=2)
        assert len(rows) == 2
        assert total == 5

    def test_empty_database(self, repo):
        assert repo.list() == ([], 0)

    def test_filter_by_single_status(self, repo, saved_receipts, app_with_db, test_data):
        test_data.set_receipt_status(app_with_db, saved_receipts[0], 'unlinked')
        rows, total = repo.list(status='unlinked')
        assert total == 1
        assert rows[0]['id'] == saved_receipts[0]

    def test_filter_by_multiple_statuses(self, repo, saved_receipts, app_with_db, test_data):
        test_data.set_receipt_status(app_with_db, saved_receipts[0], 'unlinked')
        _, total = repo.list(status=['pending', 'unlinked'])
        assert total == 5

    def test_invalid_status_rejected(self, repo):
        with pytest.raises(ValueError) as exc:
            repo.list(status='bogus')
        assert "Invalid status" in str(exc.value)

    def test_vendor_filter_is_case_insensitive(self, repo, saved_receipts):
        _, total = repo.list(vendor="walmart")
        assert total == 2

    def test_free_text_matches_vendor_or_filename(self, repo, saved_receipts):
        _, vendor_hits = repo.list(q="COSTCO")
        assert vendor_hits == 1
        _, filename_hits = repo.list(q="receipt_003")
        assert filename_hits == 1

    def test_date_bounds_are_inclusive(self, repo, saved_receipts):
        _, total = repo.list(date_from=datetime(2024, 1, 16), date_to=datetime(2024, 1, 18))
        assert total == 3

    def test_date_bounds_accept_strings(self, repo, saved_receipts):
        _, total = repo.list(date_from="2024-01-19")
        assert total == 1

    def test_amount_bounds(self, repo, saved_receipts):
        _, total = repo.list(amount_min=40.00, amount_max=70.00)
        assert total == 2

    def test_min_confidence(self, repo, saved_receipts):
        _, total = repo.list(min_confidence=3)
        assert total == 3

    def test_sort_by_amount_ascending(self, repo, saved_receipts):
        rows, _ = repo.list(sort='amount', direction='asc')
        amounts = [r['amount'] for r in rows]
        assert amounts == sorted(amounts)

    def test_sort_by_vendor_descending(self, repo, saved_receipts):
        rows, _ = repo.list(sort='vendor', direction='desc')
        assert [r['vendor'] for r in rows][0] == "WALMART"

    def test_null_dates_sort_last(self, repo, saved_receipts, sample_receipt):
        repo.save(make_receipt(date=None, stored_filename="no_date.pdf",
                               original_filename=Path("no_date.pdf")))
        rows, _ = repo.list(sort='date', direction='asc')
        assert rows[-1]['date'] is None

    def test_invalid_sort_rejected(self, repo):
        with pytest.raises(ValueError):
            repo.list(sort='nope')

    def test_invalid_direction_rejected(self, repo):
        with pytest.raises(ValueError):
            repo.list(direction='sideways')

    @pytest.mark.parametrize('kwargs', [{'limit': 0}, {'offset': -1}])
    def test_invalid_paging_rejected(self, repo, kwargs):
        with pytest.raises(ValueError):
            repo.list(**kwargs)

    def test_total_ignores_paging(self, repo, saved_receipts):
        rows, total = repo.list(limit=1, offset=3)
        assert len(rows) == 1
        assert total == 5


class TestCountByStatus:

    def test_every_status_key_present(self, repo):
        assert repo.count_by_status() == {'pending': 0, 'unlinked': 0, 'linked': 0}

    def test_counts_by_status(self, repo, saved_receipts, app_with_db, test_data):
        test_data.set_receipt_status(app_with_db, saved_receipts[0], 'unlinked')
        test_data.set_receipt_status(app_with_db, saved_receipts[1], 'linked')
        assert repo.count_by_status() == {'pending': 3, 'unlinked': 1, 'linked': 1}


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
class TestUpdate:

    def test_update_vendor_leaves_other_fields(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        updated = repo.update(receipt_id, vendor="TARGET")
        assert updated['vendor'] == "TARGET"
        assert updated['amount'] == sample_receipt.amount

    def test_update_amount(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert repo.update(receipt_id, amount=99.99)['amount'] == 99.99

    def test_update_date(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        new_date = datetime(2024, 2, 1)
        assert repo.update(receipt_id, date=new_date)['date'].date() == new_date.date()

    def test_update_confidence(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert repo.update(receipt_id, confidence=2)['confidence'] == 2

    def test_update_raw_text(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert repo.update(receipt_id, raw_text="new text")['raw_text'] == "new text"

    def test_update_multiple_fields(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        updated = repo.update(receipt_id, vendor="COSTCO", amount=150.00, confidence=3)
        assert (updated['vendor'], updated['amount'], updated['confidence']) == (
            "COSTCO", 150.00, 3
        )

    def test_update_persists(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        repo.update(receipt_id, vendor="PERSISTED")
        assert repo.get_by_id(receipt_id)['vendor'] == "PERSISTED"

    def test_no_fields_returns_current_row(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert repo.update(receipt_id) == repo.get_by_id(receipt_id)

    def test_missing_receipt_returns_none(self, repo):
        assert repo.update(999, vendor="TEST") is None

    @pytest.mark.parametrize('field', ['vendor', 'amount', 'date', 'confidence', 'raw_text'])
    def test_none_clears_the_field(self, repo, sample_receipt, field):
        receipt_id = repo.save(sample_receipt)
        assert repo.update(receipt_id, **{field: None})[field] is None

    def test_touches_updated_at(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        original = repo.get_by_id(receipt_id)
        time.sleep(0.01)
        repo.update(receipt_id, vendor="UPDATED")
        assert repo.get_by_id(receipt_id)['updated_at'] != original['updated_at']

    def test_check_constraint_violation_wrapped(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        with pytest.raises(DatabaseError):
            repo.update(receipt_id, amount=-5.00)


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #
class TestDelete:

    def test_returns_deleted_row(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        deleted = repo.delete(receipt_id)
        assert deleted['id'] == receipt_id
        assert deleted['vendor'] == sample_receipt.vendor
        assert repo.get_by_id(receipt_id) is None

    def test_missing_returns_none(self, repo):
        assert repo.delete(999) is None

    def test_only_deletes_the_target(self, repo, saved_receipts):
        repo.delete(saved_receipts[2])
        remaining = [r['id'] for r in repo.get_all()]
        assert saved_receipts[2] not in remaining
        assert len(remaining) == len(saved_receipts) - 1

    def test_cascades_link_and_clears_mirror(
        self, repo, sample_receipt, app_with_db, make_transaction
    ):
        """Deleting a receipt removes its link row and nulls transactions.receipt_id."""
        from src.services.receipt_links import ReceiptLinkService

        receipt_id = repo.save(sample_receipt)
        txn_id = make_transaction()
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, txn_id)

        repo.delete(receipt_id)

        with repo.db.get_connection() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM receipt_links WHERE receipt_id = ?", (receipt_id,)
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT receipt_id FROM transactions WHERE id = ?", (txn_id,)
            ).fetchone()[0] is None


# --------------------------------------------------------------------------- #
# get_stats
# --------------------------------------------------------------------------- #
class TestGetStats:

    def test_empty_database(self, repo):
        stats = repo.get_stats()
        assert stats['total_receipts'] == 0
        assert stats['total_amount'] is None
        assert stats['avg_amount'] is None
        assert stats['unique_vendors'] == 0
        assert stats['top_vendors'] == []

    def test_aggregates(self, repo, saved_receipts, multiple_receipts):
        stats = repo.get_stats()
        amounts = [r.amount for r in multiple_receipts]

        assert stats['total_receipts'] == 5
        assert stats['total_amount'] == pytest.approx(sum(amounts))
        assert stats['avg_amount'] == pytest.approx(sum(amounts) / len(amounts))
        assert stats['avg_confidence'] == pytest.approx(12 / 5)
        assert stats['unique_vendors'] == 3
        assert stats['high_confidence_count'] == 3

    def test_date_range(self, repo, saved_receipts):
        stats = repo.get_stats()
        assert stats['earliest_date'] == '2024-01-15'
        assert stats['latest_date'] == '2024-01-19'

    def test_top_vendors_counts_and_totals(self, repo, saved_receipts):
        vendors = {v['vendor']: v for v in repo.get_stats()['top_vendors']}
        assert vendors['WALMART']['count'] == 2
        assert vendors['WALMART']['total'] == pytest.approx(25.99 + 67.89)
        assert vendors['COSTCO']['count'] == 1

    def test_top_vendors_capped_at_ten(self, repo):
        for i in range(15):
            repo.save(make_receipt(
                original_filename=Path(f"receipt_{i}.pdf"),
                processed_images={},
                extracted_text=f"VENDOR_{i}",
                selected_method="test",
                vendor=f"VENDOR_{i}",
                date=datetime(2024, 1, 1),
                amount=10.00,
                stored_filename=f"stored_{i}.pdf",
                file_path=Path(f"/data/{i}.pdf"),
            ))
        assert len(repo.get_stats()['top_vendors']) == 10


# --------------------------------------------------------------------------- #
# row deserialization
# --------------------------------------------------------------------------- #
class TestRowDeserialization:

    def test_metadata_parsed_to_dict(self, repo, sample_receipt):
        receipt = repo.get_by_id(repo.save(sample_receipt))
        assert isinstance(receipt['metadata'], dict)
        assert 'selected_method' in receipt['metadata']

    def test_invalid_metadata_json_becomes_empty_dict(self, repo, sample_receipt, db_manager):
        receipt_id = repo.save(sample_receipt)
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE receipts SET metadata = ? WHERE id = ?",
                ("invalid json{", receipt_id),
            )
        assert repo.get_by_id(receipt_id)['metadata'] == {}

    def test_date_parsed_to_datetime(self, repo, sample_receipt):
        assert isinstance(repo.get_by_id(repo.save(sample_receipt))['date'], datetime)

    def test_null_date_stays_none(self, repo, sample_receipt):
        sample_receipt.date = None
        assert repo.get_by_id(repo.save(sample_receipt))['date'] is None

    def test_unparseable_date_left_as_is(self, repo, sample_receipt, db_manager):
        receipt_id = repo.save(sample_receipt)
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE receipts SET date = ? WHERE id = ?", ("not-a-date", receipt_id)
            )
        assert repo.get_by_id(receipt_id)['date'] == "not-a-date"


# --------------------------------------------------------------------------- #
# edge cases
# --------------------------------------------------------------------------- #
class TestEdgeCases:

    def test_empty_vendor_string(self, repo, sample_receipt):
        sample_receipt.vendor = ""
        assert repo.get_by_id(repo.save(sample_receipt))['vendor'] == ""

    def test_very_long_vendor_name(self, repo, sample_receipt):
        sample_receipt.vendor = "A" * 1000
        assert len(repo.get_by_id(repo.save(sample_receipt))['vendor']) == 1000

    def test_zero_amount(self, repo, sample_receipt):
        sample_receipt.amount = 0.0
        assert repo.get_by_id(repo.save(sample_receipt))['amount'] == 0.0

    def test_very_large_amount(self, repo, sample_receipt):
        sample_receipt.amount = 999999.99
        assert repo.get_by_id(repo.save(sample_receipt))['amount'] == 999999.99

    def test_special_characters_in_filename(self, repo, sample_receipt):
        sample_receipt.original_filename = Path("receipt's & file (2024).pdf")
        sample_receipt.stored_filename = "stored_receipt's_&_file_(2024).pdf"
        saved = repo.get_by_id(repo.save(sample_receipt))
        assert saved['original_filename'] == str(sample_receipt.original_filename)

    def test_unicode_in_vendor_name(self, repo, sample_receipt):
        sample_receipt.vendor = "Café Müller"
        assert repo.get_by_id(repo.save(sample_receipt))['vendor'] == "Café Müller"

    def test_very_long_text_field(self, repo, sample_receipt):
        sample_receipt.extracted_text = "text " * 10000
        assert len(repo.get_by_id(repo.save(sample_receipt))['raw_text']) > 40000


# --------------------------------------------------------------------------- #
# integration
# --------------------------------------------------------------------------- #
class TestIntegration:

    @pytest.mark.integration
    def test_full_receipt_lifecycle(self, repo, sample_receipt):
        receipt_id = repo.save(sample_receipt)
        assert repo.get_by_id(receipt_id)['vendor'] == sample_receipt.vendor

        assert repo.update(receipt_id, vendor="UPDATED VENDOR")['vendor'] == "UPDATED VENDOR"
        assert repo.delete(receipt_id)['id'] == receipt_id
        assert repo.get_by_id(receipt_id) is None

    @pytest.mark.integration
    def test_complex_query_scenario(self, repo, saved_receipts):
        receipts = repo.get_all(vendor="WALMART", min_confidence=2)
        assert receipts
        assert all(r['vendor'] == "WALMART" and r['confidence'] >= 2 for r in receipts)
        assert repo.get_stats()['total_receipts'] == len(saved_receipts)


# --------------------------------------------------------------------------- #
# error wrapping
# --------------------------------------------------------------------------- #
class TestErrorWrapping:

    @pytest.fixture
    def broken_repo(self, repo, monkeypatch):
        class Boom:
            def get_connection(self):
                raise RuntimeError("connection exploded")

            def transaction(self):
                raise RuntimeError("connection exploded")

        # `db` is a property resolving the global manager, so patch the resolver
        # the repository module imports.
        monkeypatch.setattr(
            'src.database.repositories.receipts.get_manager', lambda: Boom()
        )
        return repo

    @pytest.mark.parametrize('call', [
        lambda r: r.save(make_receipt()),
        lambda r: r.get_all(),
        lambda r: r.get_by_id(1),
        lambda r: r.count_by_status(),
        lambda r: r.update(1, vendor='x'),
        lambda r: r.delete(1),
        lambda r: r.get_stats(),
    ])
    def test_db_failures_surface_as_database_error(self, broken_repo, call):
        with pytest.raises(DatabaseError):
            call(broken_repo)

    @pytest.mark.xfail(
        reason="list() logs the error but never re-raises, so it silently "
               "returns None instead of raising DatabaseError - backlog",
        strict=True,
    )
    def test_list_failure_surfaces_as_database_error(self, broken_repo):
        with pytest.raises(DatabaseError):
            broken_repo.list()