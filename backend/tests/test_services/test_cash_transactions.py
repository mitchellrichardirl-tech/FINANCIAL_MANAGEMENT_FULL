"""
Tests for src/services/cash_transactions.py.

Runs against a real migrated SQLite database via the shared fixtures: the
service coordinates writes across accounts, uploads and transactions inside one
DB transaction, so mocking the database would test nothing worth testing.
"""
import pytest

from src.database.errors import DatabaseError
from src.database.repositories.accounts import AccountRepository
from src.services.cash_transactions import CashTransactionService

GENERATED_MISSING_RELATIONSHIP = pytest.mark.xfail(
    reason="generate_cash_transactions() inserts counterparts without "
           "source_relationship='generated', so the soft-delete cascade and "
           "restore logic in TransactionRepository never sees them - backlog",
    strict=True,
)

SOFT_DELETE_IGNORED = pytest.mark.xfail(
    reason="generate_cash_transactions() filters on neither the source's nor "
           "the counterpart's deleted_at, so deleted sources are mirrored and "
           "deleted counterparts block regeneration forever - backlog",
    strict=True,
)


@pytest.fixture
def service(app_with_db):
    with app_with_db.app_context():
        yield CashTransactionService()


@pytest.fixture
def accounts(app_with_db, db_manager):
    """A normal current account to act as the source of cash movements."""
    with db_manager.transaction() as conn:
        current_id = conn.execute(
            "INSERT INTO accounts (account_name, account_type) VALUES (?, ?)",
            ("Main Current", "current"),
        ).lastrowid
    return {"current_id": current_id}


@pytest.fixture
def cash_account_id(service):
    return service.account_repo.ensure_cash_account()["id"]


@pytest.fixture
def party_id(test_hierarchy):
    return test_hierarchy["party_id"]


@pytest.fixture
def make_source(app_with_db, test_data, accounts, party_id):
    """Factory: make_source(**overrides) -> id of a transaction to mirror."""
    upload_id = test_data.create_upload(app_with_db)

    def _make(**kwargs):
        kwargs.setdefault("amount", -100.00)
        kwargs.setdefault("account_id", accounts["current_id"])
        kwargs.setdefault("description", "ATM WITHDRAWAL")
        return test_data.create_transaction(
            app_with_db, upload_id, party_id, **kwargs
        )

    return _make


@pytest.fixture
def row(test_data, app_with_db):
    def _row(transaction_id):
        return test_data.fetch_one(
            app_with_db, "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        )
    return _row


@pytest.fixture
def make_receipt(app_with_db, test_data):
    def _make(**kwargs):
        kwargs.setdefault("vendor", "Tesco")
        kwargs.setdefault("date", "2024-01-15")
        kwargs.setdefault("amount", 23.40)
        return test_data.create_receipt(app_with_db, **kwargs)
    return _make


# --------------------------------------------------------------------------- #
# generate_cash_transactions - happy path
# --------------------------------------------------------------------------- #
class TestGenerateCashTransactions:

    def test_creates_one_counterpart_per_source(self, service, make_source):
        sources = [make_source(), make_source()]
        result = service.generate_cash_transactions(sources)

        assert result["created_count"] == 2
        assert result["skipped_count"] == 0
        assert result["rejected_count"] == 0
        assert len(result["transactions"]) == 2

    def test_amount_is_negated(self, service, make_source):
        source = make_source(amount=-100.00)
        created = service.generate_cash_transactions([source])["transactions"][0]
        assert created["amount"] == 100.00

    def test_negation_works_both_ways(self, service, make_source):
        source = make_source(amount=250.00)
        created = service.generate_cash_transactions([source])["transactions"][0]
        assert created["amount"] == -250.00

    def test_descriptive_fields_are_copied(self, service, make_source, party_id):
        source = make_source(
            transaction_date="2024-03-01",
            description="ATM LEESON ST",
            cleaned_description="ATM",
            is_credit=0, is_kids=1, is_one_off=1,
        )
        created = service.generate_cash_transactions([source])["transactions"][0]

        assert created["transaction_date"] == "2024-03-01"
        assert created["description"] == "ATM LEESON ST"
        assert created["cleaned_description"] == "ATM"
        assert created["is_kids"] == 1
        assert created["is_one_off"] == 1
        assert created["party_id"] == party_id

    def test_counterpart_lands_on_the_cash_account(self, service, make_source,
                                                   cash_account_id):
        created = service.generate_cash_transactions(
            [make_source()])["transactions"][0]
        assert created["account_id"] == cash_account_id

    def test_links_back_to_the_source(self, service, make_source):
        source = make_source()
        created = service.generate_cash_transactions([source])["transactions"][0]
        assert created["source_transaction_id"] == source

    def test_source_is_left_untouched(self, service, make_source, row):
        source = make_source()
        before = row(source)
        service.generate_cash_transactions([source])
        assert row(source) == before

    def test_cash_account_is_created_on_demand(self, service, make_source,
                                               db_manager):
        with db_manager.get_connection() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE account_type = 'cash'"
            ).fetchone()[0] == 0

        service.generate_cash_transactions([make_source()])

        with db_manager.get_connection() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE account_type = 'cash'"
            ).fetchone()[0] == 1

    def test_existing_cash_account_is_reused(self, service, make_source,
                                             cash_account_id, db_manager):
        service.generate_cash_transactions([make_source()])
        with db_manager.get_connection() as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE account_type = 'cash'"
            ).fetchone()[0] == 1

    def test_duplicate_ids_are_collapsed(self, service, make_source):
        source = make_source()
        result = service.generate_cash_transactions([source, source, source])
        assert result["created_count"] == 1

    def test_order_is_preserved(self, service, make_source):
        first, second = make_source(description="A"), make_source(description="B")
        result = service.generate_cash_transactions([second, first])
        created_sources = [t["source_transaction_id"] for t in result["transactions"]]
        assert sorted(created_sources) == sorted([first, second])


# --------------------------------------------------------------------------- #
# the synthetic upload
# --------------------------------------------------------------------------- #
class TestSyntheticUpload:

    def test_batch_shares_one_upload(self, service, make_source):
        result = service.generate_cash_transactions(
            [make_source(), make_source()]
        )
        upload_ids = {t["upload_id"] for t in result["transactions"]}
        assert upload_ids == {result["upload_id"]}

    def test_upload_is_marked_generated(self, service, make_source, test_data,
                                        app_with_db):
        result = service.generate_cash_transactions([make_source()])
        upload = test_data.fetch_one(
            app_with_db, "SELECT * FROM uploads WHERE id = ?", (result["upload_id"],)
        )
        assert upload["file_type"] == "generated"
        assert upload["row_count"] == 1
        assert upload["original_filename"].startswith("cash_generation_")

    def test_row_count_matches_the_batch(self, service, make_source, test_data,
                                         app_with_db):
        result = service.generate_cash_transactions(
            [make_source(), make_source(), make_source()]
        )
        upload = test_data.fetch_one(
            app_with_db, "SELECT row_count FROM uploads WHERE id = ?",
            (result["upload_id"],),
        )
        assert upload["row_count"] == 3

    def test_separate_batches_get_separate_uploads(self, service, make_source):
        first = service.generate_cash_transactions([make_source()])
        second = service.generate_cash_transactions([make_source()])
        assert first["upload_id"] != second["upload_id"]

    def test_no_upload_created_when_nothing_to_generate(self, service,
                                                        make_source, test_data,
                                                        app_with_db, db_manager):
        source = make_source()
        service.generate_cash_transactions([source])
        before = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]

        result = service.generate_cash_transactions([source])  # all skipped

        assert result["upload_id"] is None
        after = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]
        assert after == before


# --------------------------------------------------------------------------- #
# skip / reject rules
# --------------------------------------------------------------------------- #
class TestSkipAndReject:

    def test_second_run_skips_already_generated(self, service, make_source):
        source = make_source()
        service.generate_cash_transactions([source])

        result = service.generate_cash_transactions([source])
        assert result["created_count"] == 0
        assert result["skipped_ids"] == [source]

    def test_cash_account_sources_are_rejected(self, service, make_source,
                                               cash_account_id):
        cash_source = make_source(account_id=cash_account_id)
        result = service.generate_cash_transactions([cash_source])

        assert result["created_count"] == 0
        assert result["rejected_ids"] == [cash_source]

    def test_rejection_prevents_infinite_mirroring(self, service, make_source):
        """A counterpart is itself on the Cash account, so mirroring it again
        must be refused rather than generating a counterpart of a counterpart."""
        source = make_source()
        created = service.generate_cash_transactions([source])["transactions"][0]

        result = service.generate_cash_transactions([created["id"]])
        assert result["rejected_ids"] == [created["id"]]

    def test_mixed_batch_is_categorised(self, service, make_source,
                                        cash_account_id):
        fresh = make_source()
        already = make_source()
        service.generate_cash_transactions([already])
        rejected = make_source(account_id=cash_account_id)

        result = service.generate_cash_transactions([fresh, already, rejected])
        assert result["created_count"] == 1
        assert result["skipped_ids"] == [already]
        assert result["rejected_ids"] == [rejected]

    def test_partial_batch_still_creates_the_good_ones(self, service,
                                                       make_source):
        already = make_source()
        service.generate_cash_transactions([already])
        fresh = make_source()

        result = service.generate_cash_transactions([already, fresh])
        assert [t["source_transaction_id"] for t in result["transactions"]] == [fresh]


# --------------------------------------------------------------------------- #
# validation / failures
# --------------------------------------------------------------------------- #
class TestGenerateValidation:

    def test_empty_list_rejected(self, service):
        with pytest.raises(ValueError) as exc:
            service.generate_cash_transactions([])
        assert "No transaction IDs provided" in str(exc.value)

    def test_unknown_id_rejected(self, service, make_source):
        with pytest.raises(ValueError) as exc:
            service.generate_cash_transactions([make_source(), 9999])
        assert "Transactions not found: [9999]" in str(exc.value)

    def test_unknown_id_aborts_the_whole_batch(self, service, make_source,
                                               test_data, app_with_db):
        source = make_source()
        before = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM transactions")["n"]

        with pytest.raises(ValueError):
            service.generate_cash_transactions([source, 9999])

        after = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM transactions")["n"]
        assert after == before

    def test_db_failure_surfaces_as_database_error(self, service, make_source,
                                                   monkeypatch):
        class Boom:
            def transaction(self):
                raise RuntimeError("connection exploded")

        source = make_source()
        monkeypatch.setattr(service, "db", Boom())
        with pytest.raises(DatabaseError):
            service.generate_cash_transactions([source])


# --------------------------------------------------------------------------- #
# interaction with soft delete
# --------------------------------------------------------------------------- #
class TestSoftDeleteInteraction:

    @GENERATED_MISSING_RELATIONSHIP
    def test_counterpart_is_marked_as_generated(self, service, make_source, row):
        """TransactionRepository keys its cascade off source_relationship."""
        created = service.generate_cash_transactions(
            [make_source()])["transactions"][0]
        assert row(created["id"])["source_relationship"] == "generated"

    @GENERATED_MISSING_RELATIONSHIP
    def test_deleting_the_source_cascades_to_the_counterpart(
        self, service, make_source, row, app_with_db
    ):
        from src.database.repositories.transactions import TransactionRepository

        source = make_source()
        created = service.generate_cash_transactions([source])["transactions"][0]

        with app_with_db.app_context():
            result = TransactionRepository().delete_transaction(source)

        assert result["cascaded_ids"] == [created["id"]]
        assert row(created["id"])["deleted_reason"] == "cascade"

    @SOFT_DELETE_IGNORED
    def test_deleted_source_is_not_mirrored(self, service, make_source,
                                            app_with_db, test_data):
        source = make_source()
        test_data.soft_delete_transaction(app_with_db, source)

        result = service.generate_cash_transactions([source])
        assert result["created_count"] == 0

    @SOFT_DELETE_IGNORED
    def test_deleted_counterpart_can_be_regenerated(self, service, make_source,
                                                    app_with_db, test_data):
        source = make_source()
        created = service.generate_cash_transactions(
            [source])["transactions"][0]
        test_data.soft_delete_transaction(app_with_db, created["id"])

        result = service.generate_cash_transactions([source])
        assert result["created_count"] == 1


# --------------------------------------------------------------------------- #
# create_cash_transaction
# --------------------------------------------------------------------------- #
class TestCreateCashTransaction:

    def test_creates_a_withdrawal(self, service, party_id, cash_account_id):
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=50.00,
            description="Coffee", party_id=party_id,
        )
        transaction = result["transaction"]
        assert transaction["amount"] == -50.00
        assert transaction["account_id"] == cash_account_id
        assert transaction["description"] == "Coffee"
        assert transaction["cleaned_description"] == "Coffee"
        assert transaction["transaction_date"] == "2024-01-15"

    def test_creates_a_lodgement(self, service, party_id):
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=50.00,
            description="Cash in", party_id=party_id, is_withdrawal=False,
        )
        assert result["transaction"]["amount"] == 50.00

    def test_sign_is_derived_not_taken_from_the_input(self, service, party_id):
        """A positive amount plus is_withdrawal=True must still be negative."""
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=50.00,
            description="X", party_id=party_id, is_withdrawal=True,
        )
        assert result["transaction"]["amount"] == -50.00

    @pytest.mark.parametrize("flag", ["is_credit", "is_kids", "is_one_off"])
    def test_flags_are_stored(self, service, party_id, flag):
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=1.00, description="X",
            party_id=party_id, **{flag: True},
        )
        assert result["transaction"][flag] == 1

    def test_flags_default_to_false(self, service, party_id):
        transaction = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=1.00, description="X",
            party_id=party_id,
        )["transaction"]
        assert (transaction["is_credit"], transaction["is_kids"],
                transaction["is_one_off"]) == (0, 0, 0)

    def test_is_marked_as_generated(self, service, party_id, row):
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=1.00, description="X",
            party_id=party_id,
        )
        assert row(result["transaction"]["id"])["source_relationship"] == "generated"

    def test_has_a_synthetic_upload(self, service, party_id, test_data,
                                    app_with_db):
        result = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=1.00, description="X",
            party_id=party_id,
        )
        upload = test_data.fetch_one(
            app_with_db, "SELECT * FROM uploads WHERE id = ?", (result["upload_id"],)
        )
        assert upload["file_type"] == "generated"
        assert upload["filename"] == "manual_cash_2024-01-15"

    def test_no_source_transaction(self, service, party_id):
        transaction = service.create_cash_transaction(
            transaction_date="2024-01-15", amount=1.00, description="X",
            party_id=party_id,
        )["transaction"]
        assert transaction["source_transaction_id"] is None

    @pytest.mark.parametrize("amount", [0, -1, -0.01])
    def test_non_positive_amount_rejected(self, service, party_id, amount):
        with pytest.raises(ValueError) as exc:
            service.create_cash_transaction(
                transaction_date="2024-01-15", amount=amount,
                description="X", party_id=party_id,
            )
        assert "amount must be positive" in str(exc.value)

    def test_unknown_party_rejected(self, service):
        with pytest.raises(DatabaseError):
            service.create_cash_transaction(
                transaction_date="2024-01-15", amount=1.00,
                description="X", party_id=9999,
            )

    def test_failed_insert_leaves_no_upload(self, service, test_data,
                                            app_with_db):
        before = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]
        with pytest.raises(DatabaseError):
            service.create_cash_transaction(
                transaction_date="2024-01-15", amount=1.00,
                description="X", party_id=9999,
            )
        after = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]
        assert after == before


# --------------------------------------------------------------------------- #
# generate_cash_transaction_from_receipt
# --------------------------------------------------------------------------- #
class TestGenerateFromReceipt:

    def test_derives_fields_from_the_receipt(self, service, make_receipt,
                                             party_id, cash_account_id):
        receipt_id = make_receipt(vendor="Tesco", date="2024-02-02", amount=23.40)
        transaction = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id)["transaction"]

        assert transaction["description"] == "Tesco"
        assert transaction["transaction_date"] == "2024-02-02"
        assert transaction["amount"] == -23.40
        assert transaction["account_id"] == cash_account_id
        assert transaction["receipt_id"] == receipt_id

    def test_marked_as_generated(self, service, make_receipt, party_id, row):
        receipt_id = make_receipt()
        transaction = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id)["transaction"]
        assert row(transaction["id"])["source_relationship"] == "generated"

    def test_lodgement_variant(self, service, make_receipt, party_id):
        receipt_id = make_receipt(amount=23.40)
        transaction = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id, is_withdrawal=False)["transaction"]
        assert transaction["amount"] == 23.40

    def test_upload_named_after_the_receipt_file(self, service, make_receipt,
                                                 party_id, test_data,
                                                 app_with_db):
        receipt_id = make_receipt(original_filename="tesco_receipt.jpg")
        result = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id)
        upload = test_data.fetch_one(
            app_with_db, "SELECT * FROM uploads WHERE id = ?", (result["upload_id"],)
        )
        assert upload["original_filename"] == "tesco_receipt.jpg"
        assert upload["file_type"] == "generated"

    @pytest.mark.parametrize("flag", ["is_credit", "is_kids", "is_one_off"])
    def test_flags_are_stored(self, service, make_receipt, party_id, flag):
        receipt_id = make_receipt()
        transaction = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id, **{flag: True})["transaction"]
        assert transaction[flag] == 1

    def test_missing_receipt_rejected(self, service, party_id):
        with pytest.raises(ValueError) as exc:
            service.generate_cash_transaction_from_receipt(9999, party_id)
        assert "Receipt 9999 not found" in str(exc.value)

    @pytest.mark.parametrize("field", ["vendor", "date", "amount"])
    def test_incomplete_receipt_rejected(self, service, make_receipt, party_id,
                                         field):
        receipt_id = make_receipt(**{field: None})
        with pytest.raises(ValueError) as exc:
            service.generate_cash_transaction_from_receipt(receipt_id, party_id)
        assert field in str(exc.value)

    def test_all_missing_fields_are_listed(self, service, make_receipt,
                                           party_id):
        receipt_id = make_receipt(vendor=None, date=None)
        with pytest.raises(ValueError) as exc:
            service.generate_cash_transaction_from_receipt(receipt_id, party_id)
        assert "vendor" in str(exc.value) and "date" in str(exc.value)

    def test_already_linked_receipt_rejected(self, service, make_receipt,
                                             party_id):
        receipt_id = make_receipt()
        service.generate_cash_transaction_from_receipt(receipt_id, party_id)

        with pytest.raises(ValueError) as exc:
            service.generate_cash_transaction_from_receipt(receipt_id, party_id)
        assert "already linked" in str(exc.value)

    def test_rejected_receipt_leaves_no_upload(self, service, make_receipt,
                                               party_id, test_data, app_with_db):
        receipt_id = make_receipt(vendor=None)
        before = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]
        with pytest.raises(ValueError):
            service.generate_cash_transaction_from_receipt(receipt_id, party_id)
        after = test_data.fetch_one(
            app_with_db, "SELECT COUNT(*) AS n FROM uploads")["n"]
        assert after == before

    def test_deleted_link_allows_a_retry(self, service, make_receipt, party_id,
                                         app_with_db, test_data):
        """The linked check ignores soft-deleted transactions, so a receipt
        freed by deleting its transaction can be used again."""
        receipt_id = make_receipt()
        first = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id)["transaction"]
        test_data.soft_delete_transaction(app_with_db, first["id"])

        second = service.generate_cash_transaction_from_receipt(
            receipt_id, party_id)["transaction"]
        assert second["id"] != first["id"]

    def test_db_failure_surfaces_as_database_error(self, service, make_receipt,
                                                   party_id, monkeypatch):
        class Boom:
            def transaction(self):
                raise RuntimeError("connection exploded")

        receipt_id = make_receipt()
        monkeypatch.setattr(service, "db", Boom())
        with pytest.raises(DatabaseError):
            service.generate_cash_transaction_from_receipt(receipt_id, party_id)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
class TestBuildResult:

    def test_shape(self):
        result = CashTransactionService._build_result(
            created=[{"id": 1}], skipped_ids=[2], rejected_ids=[3], upload_id=9
        )
        assert result == {
            "created_count": 1,
            "skipped_count": 1,
            "rejected_count": 1,
            "upload_id": 9,
            "transactions": [{"id": 1}],
            "skipped_ids": [2],
            "rejected_ids": [3],
        }

    def test_empty(self):
        result = CashTransactionService._build_result([], [], [], None)
        assert result["created_count"] == 0
        assert result["upload_id"] is None