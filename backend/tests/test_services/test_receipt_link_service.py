"""
Behavioural tests for ReceiptLinkService — the single writer for
receipt <-> transaction link state.
Invariant under test: after any operation,
    receipt_links row exists
    <=> transactions.receipt_id is set
    <=> receipts.status == 'linked'
"""

import pytest
from src.api.utils.errors import AppError, ErrorCode
from src.services.receipt_links import ReceiptLinkService

# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def service(app_with_db):
    with app_with_db.app_context():
        yield ReceiptLinkService()


@pytest.fixture
def pending_receipt(app_with_db, test_data):
    return test_data.create_receipt(app_with_db, status="pending", vendor=None)


@pytest.fixture
def unlinked_receipt(app_with_db, test_data):
    return test_data.create_receipt(
        app_with_db, status="unlinked", confirmed_at="2024-01-16 10:00:00.000"
    )


def _receipt(app, test_data, receipt_id):
    return test_data.fetch_one(
        app, "SELECT * FROM receipts WHERE id = ?", (receipt_id,)
    )


def _transaction(app, test_data, txn_id):
    return test_data.fetch_one(
        app, "SELECT * FROM transactions WHERE id = ?", (txn_id,)
    )


def _link(app, test_data, receipt_id):
    return test_data.fetch_one(
        app, "SELECT * FROM receipt_links WHERE receipt_id = ?", (receipt_id,)
    )


def assert_linked(app, test_data, receipt_id, txn_id, source="manual"):
    link = _link(app, test_data, receipt_id)
    assert link is not None
    assert link["transaction_id"] == txn_id
    assert link["link_source"] == source
    assert _transaction(app, test_data, txn_id)["receipt_id"] == receipt_id
    r = _receipt(app, test_data, receipt_id)
    assert r["status"] == "linked"
    assert r["confirmed_at"] is not None


def assert_not_linked(
    app, test_data, receipt_id, txn_id=None, expected_status="unlinked"
):
    assert _link(app, test_data, receipt_id) is None
    assert _receipt(app, test_data, receipt_id)["status"] == expected_status
    if txn_id is not None:
        assert _transaction(app, test_data, txn_id)["receipt_id"] is None


# --------------------------------------------------------------------------- #
# link()
# --------------------------------------------------------------------------- #


class TestLink:
    def test_links_unlinked_receipt(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        result = service.link(unlinked_receipt, live_transaction)
        assert_linked(app_with_db, test_data, unlinked_receipt, live_transaction)
        assert result["receipt"]["id"] == unlinked_receipt
        assert result["receipt"]["status"] == "linked"
        assert result["transaction"]["id"] == live_transaction
        assert result["transaction"]["receipt_id"] == unlinked_receipt

    def test_links_pending_receipt_and_confirms_it(
        self, app_with_db, test_data, service, pending_receipt, live_transaction
    ):
        service.link(pending_receipt, live_transaction)
        assert_linked(app_with_db, test_data, pending_receipt, live_transaction)

    def test_preserves_existing_confirmed_at(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        before = _receipt(app_with_db, test_data, unlinked_receipt)["confirmed_at"]
        service.link(unlinked_receipt, live_transaction)
        after = _receipt(app_with_db, test_data, unlinked_receipt)["confirmed_at"]
        assert after == before

    def test_records_link_source(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction, source="auto")
        assert_linked(
            app_with_db, test_data, unlinked_receipt, live_transaction, source="auto"
        )

    def test_rejects_unknown_link_source(
        self, service, unlinked_receipt, live_transaction
    ):
        with pytest.raises(AppError) as exc:
            service.link(unlinked_receipt, live_transaction, source="telepathy")
        assert exc.value.code == ErrorCode.INVALID_VALUE
        assert exc.value.field == "source"

    def test_receipt_not_found(self, service, live_transaction):
        with pytest.raises(AppError) as exc:
            service.link(999_999, live_transaction)
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.entity == "Receipt"
        assert exc.value.status_code == 404

    def test_transaction_not_found(self, service, unlinked_receipt):
        with pytest.raises(AppError) as exc:
            service.link(unlinked_receipt, 999_999)
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.entity == "Transaction"

    def test_soft_deleted_transaction_treated_as_not_found(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        test_data.soft_delete_transaction(app_with_db, live_transaction)
        with pytest.raises(AppError) as exc:
            service.link(unlinked_receipt, live_transaction)
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.entity == "Transaction"
        assert_not_linked(app_with_db, test_data, unlinked_receipt)

    def test_receipt_already_linked_conflicts(
        self, app_with_db, test_data, service, unlinked_receipt, make_transaction
    ):
        t1, t2 = make_transaction(), make_transaction()
        service.link(unlinked_receipt, t1)
        with pytest.raises(AppError) as exc:
            service.link(unlinked_receipt, t2)
        assert exc.value.code == ErrorCode.CONFLICT
        assert exc.value.entity == "Receipt"
        assert exc.value.status_code == 409
        assert exc.value.details.get("transaction_id") == t1
        # Original link untouched, t2 untouched
        assert_linked(app_with_db, test_data, unlinked_receipt, t1)
        assert _transaction(app_with_db, test_data, t2)["receipt_id"] is None

    def test_transaction_already_linked_conflicts(
        self, app_with_db, test_data, service, live_transaction
    ):
        r1 = test_data.create_receipt(app_with_db, status="unlinked")
        r2 = test_data.create_receipt(app_with_db, status="unlinked")
        service.link(r1, live_transaction)
        with pytest.raises(AppError) as exc:
            service.link(r2, live_transaction)
        assert exc.value.code == ErrorCode.CONFLICT
        assert exc.value.entity == "Transaction"
        assert exc.value.details.get("receipt_id") == r1
        assert_linked(app_with_db, test_data, r1, live_transaction)
        assert_not_linked(app_with_db, test_data, r2)

    def test_relinking_same_pair_is_conflict_not_duplicate(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction)
        with pytest.raises(AppError) as exc:
            service.link(unlinked_receipt, live_transaction)
        assert exc.value.code == ErrorCode.CONFLICT
        assert (
            test_data.fetch_one(app_with_db, "SELECT COUNT(*) AS n FROM receipt_links")[
                "n"
            ]
            == 1
        )

    def test_legacy_mirror_only_link_is_respected(
        self, app_with_db, test_data, service, live_transaction, make_transaction
    ):
        """A transactions.receipt_id with no receipt_links row (shouldn't
        happen post-migration, but must not be silently overwritten)."""
        r_old = test_data.create_receipt(app_with_db, status="unlinked")
        with app_with_db.app_context():
            from src.database import connection as db

            with db.get_manager().transaction() as conn:
                conn.execute(
                    "UPDATE transactions SET receipt_id = ? WHERE id = ?",
                    (r_old, live_transaction),
                )
        r_new = test_data.create_receipt(app_with_db, status="unlinked")
        with pytest.raises(AppError) as exc:
            service.link(r_new, live_transaction)
        assert exc.value.code == ErrorCode.CONFLICT


# --------------------------------------------------------------------------- #
# unlink_receipt()
# --------------------------------------------------------------------------- #


class TestUnlinkReceipt:
    def test_unlinks(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction)
        result = service.unlink_receipt(unlinked_receipt)
        assert_not_linked(app_with_db, test_data, unlinked_receipt, live_transaction)
        assert result["receipt"]["status"] == "unlinked"
        assert result["transaction"]["id"] == live_transaction
        assert result["transaction"]["receipt_id"] is None

    def test_keeps_confirmed_at(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction)
        service.unlink_receipt(unlinked_receipt)
        assert (
            _receipt(app_with_db, test_data, unlinked_receipt)["confirmed_at"]
            is not None
        )

    def test_unlink_not_linked_is_noop(
        self, app_with_db, test_data, service, unlinked_receipt
    ):
        result = service.unlink_receipt(unlinked_receipt)
        assert result["receipt"]["status"] == "unlinked"
        assert result["transaction"] is None
        assert_not_linked(app_with_db, test_data, unlinked_receipt)

    def test_unlink_pending_stays_pending(
        self, app_with_db, test_data, service, pending_receipt
    ):
        service.unlink_receipt(pending_receipt)
        assert_not_linked(
            app_with_db, test_data, pending_receipt, expected_status="pending"
        )

    def test_receipt_not_found(self, service):
        with pytest.raises(AppError) as exc:
            service.unlink_receipt(999_999)
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.entity == "Receipt"

    def test_relink_after_unlink(
        self, app_with_db, test_data, service, unlinked_receipt, make_transaction
    ):
        t1, t2 = make_transaction(), make_transaction()
        service.link(unlinked_receipt, t1)
        service.unlink_receipt(unlinked_receipt)
        service.link(unlinked_receipt, t2)
        assert_linked(app_with_db, test_data, unlinked_receipt, t2)
        assert _transaction(app_with_db, test_data, t1)["receipt_id"] is None


# --------------------------------------------------------------------------- #
# unlink_transaction()
# --------------------------------------------------------------------------- #


class TestUnlinkTransaction:
    def test_unlinks(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction)
        result = service.unlink_transaction(live_transaction)
        assert_not_linked(app_with_db, test_data, unlinked_receipt, live_transaction)
        assert result["receipt"]["id"] == unlinked_receipt
        assert result["receipt"]["status"] == "unlinked"

    def test_not_linked_is_noop(
        self, app_with_db, test_data, service, live_transaction
    ):
        result = service.unlink_transaction(live_transaction)
        assert result["receipt"] is None
        assert (
            _transaction(app_with_db, test_data, live_transaction)["receipt_id"] is None
        )

    def test_explicit_unlink_on_soft_deleted_transaction_is_allowed(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        """Delete paths call this *after* soft-deleting; it must still release the receipt."""
        service.link(unlinked_receipt, live_transaction)
        test_data.soft_delete_transaction(app_with_db, live_transaction)
        service.unlink_transaction(live_transaction)
        assert_not_linked(app_with_db, test_data, unlinked_receipt, live_transaction)

    def test_transaction_not_found(self, service):
        with pytest.raises(AppError) as exc:
            service.unlink_transaction(999_999)
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.entity == "Transaction"


# --------------------------------------------------------------------------- #
# confirm()
# --------------------------------------------------------------------------- #


class TestConfirm:
    def test_pending_becomes_unlinked(
        self, app_with_db, test_data, service, pending_receipt
    ):
        result = service.confirm(
            pending_receipt, vendor="Shop", amount=12.5, date="2024-01-15"
        )
        r = _receipt(app_with_db, test_data, pending_receipt)
        assert r["status"] == "unlinked"
        assert r["confirmed_at"] is not None
        assert r["vendor"] == "Shop"
        assert r["amount"] == 12.5
        assert result["status"] == "unlinked"

    def test_unlinked_stays_unlinked_and_keeps_confirmed_at(
        self, app_with_db, test_data, service, unlinked_receipt
    ):
        before = _receipt(app_with_db, test_data, unlinked_receipt)["confirmed_at"]
        service.confirm(unlinked_receipt, vendor="Edited")
        r = _receipt(app_with_db, test_data, unlinked_receipt)
        assert r["status"] == "unlinked"
        assert r["confirmed_at"] == before
        assert r["vendor"] == "Edited"

    def test_linked_receipt_fields_editable_but_status_unchanged(
        self, app_with_db, test_data, service, unlinked_receipt, live_transaction
    ):
        service.link(unlinked_receipt, live_transaction)
        service.confirm(unlinked_receipt, vendor="Corrected")
        assert_linked(app_with_db, test_data, unlinked_receipt, live_transaction)
        assert (
            _receipt(app_with_db, test_data, unlinked_receipt)["vendor"] == "Corrected"
        )

    def test_confirm_requires_vendor_when_transitioning_from_pending(
        self, service, pending_receipt
    ):
        with pytest.raises(AppError) as exc:
            service.confirm(pending_receipt, vendor=None)
        assert exc.value.code == ErrorCode.REQUIRED_FIELD
        assert exc.value.field == "vendor"

    def test_receipt_not_found(self, service):
        with pytest.raises(AppError) as exc:
            service.confirm(999_999, vendor="X")
        assert exc.value.code == ErrorCode.NOT_FOUND


# --------------------------------------------------------------------------- #
# Atomicity
# --------------------------------------------------------------------------- #


class TestAtomicity:
    def test_failed_link_leaves_no_partial_state(
        self,
        app_with_db,
        test_data,
        service,
        unlinked_receipt,
        live_transaction,
        monkeypatch,
    ):
        """If the last write in link() fails, nothing from earlier writes survives."""
        import src.services.receipt_links as mod

        def boom(*args, **kwargs):
            raise RuntimeError("simulated failure")

        # The implementation must route its final receipt-status write through
        # a method we can patch; name it `_mark_receipt_linked`.
        monkeypatch.setattr(mod.ReceiptLinkService, "_mark_receipt_linked", boom)
        with pytest.raises(RuntimeError):
            service.link(unlinked_receipt, live_transaction)
        assert_not_linked(app_with_db, test_data, unlinked_receipt, live_transaction)


class TestSoftDeleteInteraction:
    def test_soft_delete_keeps_receipt_linked(self, app_with_db, test_data, service, unlinked_receipt, live_transaction):
        service.link(unlinked_receipt, live_transaction)
        with app_with_db.app_context():
            from src.database.repositories.transactions import TransactionRepository
            TransactionRepository().delete_transaction(live_transaction)
        assert_linked(app_with_db, test_data, unlinked_receipt, live_transaction)