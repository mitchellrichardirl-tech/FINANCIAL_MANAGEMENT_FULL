"""
ReceiptRepository additions for link state: status/link columns on reads,
list() with filters + paging, count_by_status(). Read-only w.r.t. link
state - ReceiptLinkService is the only writer.
"""

import pytest
from src.database.repositories.receipts import ReceiptRepository
from src.services.receipt_links import ReceiptLinkService


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield ReceiptRepository()


@pytest.fixture
def link_service(app_with_db):
    with app_with_db.app_context():
        yield ReceiptLinkService()


@pytest.fixture
def make_receipt(app_with_db, test_data):
    def _make(**kwargs):
        return test_data.create_receipt(app_with_db, **kwargs)

    return _make


@pytest.fixture
def population(make_receipt, make_transaction, link_service):
    """Deterministic mixed set. Returns dict of name -> receipt id."""
    ids = {
        "pending_a": make_receipt(
            status="pending",
            vendor=None,
            date="2024-01-10",
            amount=5.00,
            original_filename="scan_001.jpg",
        ),
        "pending_b": make_receipt(
            status="pending",
            vendor="Draft Shop",
            date=None,
            amount=None,
            original_filename="scan_002.jpg",
        ),
        "unlinked_a": make_receipt(
            status="unlinked",
            vendor="Tesco",
            date="2024-01-15",
            amount=23.40,
            confirmed_at="2024-01-16 10:00:00.000",
        ),
        "unlinked_b": make_receipt(
            status="unlinked",
            vendor="tesco express",
            date="2024-01-20",
            amount=7.99,
            confirmed_at="2024-01-21 10:00:00.000",
        ),
        "unlinked_c": make_receipt(
            status="unlinked",
            vendor="Boots",
            date="2024-02-01",
            amount=150.00,
            confirmed_at="2024-02-02 10:00:00.000",
        ),
        "linked_a": make_receipt(
            status="unlinked",
            vendor="Argos",
            date="2024-01-18",
            amount=40.00,
            confirmed_at="2024-01-19 10:00:00.000",
        ),
    }
    txn = make_transaction(transaction_date="2024-01-18", amount=-40.00)
    link_service.link(ids["linked_a"], txn)
    ids["_linked_txn"] = txn
    return ids


def _ids(rows):
    return [r["id"] for r in rows]


# --------------------------------------------------------------------------- #
# Read shape
# --------------------------------------------------------------------------- #


class TestReadShape:
    def test_get_by_id_exposes_status_fields(self, repo, make_receipt):
        rid = make_receipt()  # factory default status='pending'
        row = repo.get_by_id(rid)
        assert row["status"] == "pending"
        assert row["confirmed_at"] is None
        assert row["linked_transaction_id"] is None

    def test_get_by_id_exposes_linked_transaction(self, repo, population):
        row = repo.get_by_id(population["linked_a"])
        assert row["status"] == "linked"
        assert row["linked_transaction_id"] == population["_linked_txn"]
        assert row["confirmed_at"] is not None

    def test_get_all_exposes_status_fields(self, repo, population):
        rows = repo.get_all(limit=100)
        assert all("status" in r and "linked_transaction_id" in r for r in rows)

    def test_list_rows_have_same_shape_as_get_by_id(self, repo, population):
        rows, _ = repo.list()
        direct = repo.get_by_id(rows[0]["id"])
        assert set(rows[0].keys()) == set(direct.keys())

    def test_update_cannot_touch_link_state(self, repo, population):
        """Single-writer rule: repository update has no status/confirmed_at params."""
        with pytest.raises(TypeError):
            repo.update(population["unlinked_a"], status="linked")
        with pytest.raises(TypeError):
            repo.update(population["unlinked_a"], confirmed_at="2024-01-01")

    def test_update_does_not_disturb_status(self, repo, population):
        repo.update(population["linked_a"], vendor="Argos Ltd")
        row = repo.get_by_id(population["linked_a"])
        assert row["status"] == "linked"
        assert row["linked_transaction_id"] == population["_linked_txn"]


# --------------------------------------------------------------------------- #
# list(): filters
# --------------------------------------------------------------------------- #


class TestListFilters:
    def test_no_filters_returns_everything(self, repo, population):
        rows, total = repo.list(limit=100)
        assert total == 6
        assert len(rows) == 6

    def test_filter_single_status(self, repo, population):
        rows, total = repo.list(status=["linked"])
        assert total == 1
        assert _ids(rows) == [population["linked_a"]]

    def test_filter_multiple_statuses(self, repo, population):
        rows, total = repo.list(status=["pending", "unlinked"])
        assert total == 5
        assert population["linked_a"] not in _ids(rows)

    def test_filter_status_accepts_string(self, repo, population):
        rows, total = repo.list(status="pending")
        assert total == 2

    def test_invalid_status_raises(self, repo, population):
        with pytest.raises(ValueError):
            repo.list(status=["saved"])

    def test_filter_vendor_is_case_insensitive_substring(self, repo, population):
        rows, total = repo.list(vendor="TESCO")
        assert total == 2
        assert set(_ids(rows)) == {population["unlinked_a"], population["unlinked_b"]}

    def test_filter_date_range_inclusive(self, repo, population):
        rows, total = repo.list(date_from="2024-01-15", date_to="2024-01-20")
        assert set(_ids(rows)) == {
            population["unlinked_a"],
            population["unlinked_b"],
            population["linked_a"],
        }

    def test_filter_date_from_only(self, repo, population):
        rows, _ = repo.list(date_from="2024-02-01")
        assert _ids(rows) == [population["unlinked_c"]]

    def test_filter_date_excludes_null_dates(self, repo, population):
        rows, _ = repo.list(date_from="2000-01-01")
        assert population["pending_b"] not in _ids(rows)

    def test_filter_amount_range_inclusive(self, repo, population):
        rows, _ = repo.list(amount_min=7.99, amount_max=40.00)
        assert set(_ids(rows)) == {
            population["unlinked_a"],
            population["unlinked_b"],
            population["linked_a"],
        }

    def test_filter_amount_excludes_null_amounts(self, repo, population):
        rows, _ = repo.list(amount_min=0)
        assert population["pending_b"] not in _ids(rows)

    def test_q_matches_vendor_or_filename(self, repo, population):
        rows, _ = repo.list(q="scan_00")
        assert set(_ids(rows)) == {population["pending_a"], population["pending_b"]}
        rows, _ = repo.list(q="boots")
        assert _ids(rows) == [population["unlinked_c"]]

    def test_filters_combine_with_and(self, repo, population):
        rows, total = repo.list(status=["unlinked"], vendor="tesco", amount_max=10)
        assert _ids(rows) == [population["unlinked_b"]]
        assert total == 1

    def test_total_ignores_paging(self, repo, population):
        rows, total = repo.list(status=["pending", "unlinked"], limit=2)
        assert len(rows) == 2
        assert total == 5


# --------------------------------------------------------------------------- #
# list(): paging & sorting
# --------------------------------------------------------------------------- #


class TestListPagingSorting:
    def test_default_sort_is_created_at_desc(self, repo, population):
        rows, _ = repo.list()
        assert _ids(rows) == sorted(
            _ids(rows), reverse=True
        )  # ids rise with created_at

    def test_sort_by_date_asc_nulls_last(self, repo, population):
        rows, _ = repo.list(sort="date", direction="asc")
        dates = [r["date"] for r in rows]
        assert dates[-1] is None
        non_null = [d for d in dates if d is not None]
        assert non_null == sorted(non_null)

    def test_sort_by_amount_desc(self, repo, population):
        rows, _ = repo.list(sort="amount", direction="desc")
        amounts = [r["amount"] for r in rows if r["amount"] is not None]
        assert amounts == sorted(amounts, reverse=True)

    def test_sort_by_vendor_case_insensitive(self, repo, population):
        rows, _ = repo.list(
            sort="vendor", direction="asc", status=["unlinked", "linked"]
        )
        vendors = [r["vendor"] for r in rows]
        assert vendors == sorted(vendors, key=str.lower)

    def test_invalid_sort_raises(self, repo, population):
        with pytest.raises(ValueError):
            repo.list(sort="file_path")

    def test_invalid_direction_raises(self, repo, population):
        with pytest.raises(ValueError):
            repo.list(direction="sideways")

    def test_offset(self, repo, population):
        all_rows, _ = repo.list(sort="amount", direction="asc", limit=100)
        page, _ = repo.list(sort="amount", direction="asc", limit=2, offset=2)
        assert _ids(page) == _ids(all_rows)[2:4]

    def test_limit_zero_or_negative_raises(self, repo, population):
        with pytest.raises(ValueError):
            repo.list(limit=0)
        with pytest.raises(ValueError):
            repo.list(offset=-1)

    def test_empty_result(self, repo):
        rows, total = repo.list()
        assert rows == []
        assert total == 0


# --------------------------------------------------------------------------- #
# count_by_status()
# --------------------------------------------------------------------------- #


class TestCountByStatus:
    def test_empty_database_has_all_keys(self, repo):
        assert repo.count_by_status() == {"pending": 0, "unlinked": 0, "linked": 0}

    def test_counts(self, repo, population):
        assert repo.count_by_status() == {"pending": 2, "unlinked": 3, "linked": 1}

    def test_counts_follow_link_service(self, repo, population, link_service):
        link_service.unlink_receipt(population["linked_a"])
        assert repo.count_by_status() == {"pending": 2, "unlinked": 4, "linked": 0}


# --------------------------------------------------------------------------- #
# save()
# --------------------------------------------------------------------------- #


class TestSaveStatus:
    def test_save_starts_pending(self, repo):
        from pathlib import Path

        import numpy as np
        from src.models.receipt import Receipt

        rid = repo.save(
            Receipt(
                original_filename=Path("new.jpg"),
                page_number=0,
                original_image=np.zeros((4, 4, 3), dtype=np.uint8),
                processed_images={},
                stored_filename="stored_new.jpg",
                file_path=Path("/tmp/stored_new.jpg"),
            )
        )
        row = repo.get_by_id(rid)
        assert row["status"] == "pending"
        assert row["confirmed_at"] is None
        assert row["linked_transaction_id"] is None
