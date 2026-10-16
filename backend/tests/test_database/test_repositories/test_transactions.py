"""
TransactionRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched tests are the DatabaseError-wrapping checks.
"""
import pandas as pd
import pytest

from src.database.errors import DatabaseError, TransactionRuleError
from src.database.repositories.transactions import (
    TRANSACTION_PROTECTED_FIELDS,
    TRANSACTION_UPDATABLE_FIELDS,
    TransactionRepository,
)
from src.models.transaction import Transaction

# Two methods on this repository are currently broken. They have no callers in
# src/ (the API listing route uses get_transactions_with_hierarchy instead), so
# the breakage is invisible in production today. Tests that exercise the broken
# path are marked xfail(strict) so they flip to failures the moment either is
# fixed.
MODEL_MISMATCH = pytest.mark.xfail(
    reason="get_transactions()/get_transaction_by_id() select account_name, "
           "related_party_name and receipt_filename but the Transaction "
           "dataclass has no such fields, so Transaction(**row) raises - backlog",
    strict=True,
)
LASTROWID_AFTER_EXECUTEMANY = pytest.mark.xfail(
    reason="bulk_add_transactions_from_objects() derives ids from "
           "cursor.lastrowid after executemany(), which is None on Python "
           "3.12+, so every call raises - backlog",
    strict=True,
)
BROKEN_SQL = pytest.mark.xfail(
    reason="find_receipt_match_candidates() builds its query from a literal "
           "'...' placeholder instead of a column list, so every call raises a "
           "syntax error - backlog",
    strict=True,
)


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield TransactionRepository()


@pytest.fixture
def upload_id(app_with_db, test_data):
    return test_data.create_upload(app_with_db)


@pytest.fixture
def party_id(test_hierarchy):
    return test_hierarchy['party_id']


@pytest.fixture
def account_id(db_manager):
    with db_manager.transaction() as conn:
        return conn.execute(
            "INSERT INTO accounts (account_name, account_type) VALUES (?, ?)",
            ("Main Checking", "checking"),
        ).lastrowid


def make_model(upload_id, party_id, **overrides) -> Transaction:
    """Build a Transaction model instance for the insert methods."""
    defaults = dict(
        id=None,
        transaction_date='2024-01-15',
        amount=-10.00,
        description='TESCO STORES 1234',
        created_at=None,
        is_credit=False,
        account_id=None,
        upload_id=upload_id,
        party_id=party_id,
        is_kids=False,
        is_one_off=False,
        cleaned_description='TESCO',
    )
    defaults.update(overrides)
    return Transaction(**defaults)


@pytest.fixture
def make_txn(app_with_db, test_data, upload_id, party_id):
    """Factory: make_txn(**overrides) -> transaction id."""
    def _make(**kwargs):
        kwargs.setdefault('amount', -10.00)
        return test_data.create_transaction(app_with_db, upload_id, party_id, **kwargs)
    return _make


@pytest.fixture
def link_child(db_manager):
    """Attach a child to a parent: link_child(child_id, parent_id, 'generated')."""
    def _link(child_id, parent_id, relationship):
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE transactions SET source_transaction_id = ?, "
                "source_relationship = ? WHERE id = ?",
                (parent_id, relationship, child_id),
            )
    return _link


@pytest.fixture
def row(test_data, app_with_db):
    """Read a transaction row straight from the table, bypassing the repo."""
    def _row(transaction_id):
        return test_data.fetch_one(
            app_with_db, 'SELECT * FROM transactions WHERE id = ?', (transaction_id,)
        )
    return _row


# --------------------------------------------------------------------------- #
# field allowlists
# --------------------------------------------------------------------------- #
class TestFieldAllowlists:
    """The allowlists are a security boundary, so assert their contents."""

    def test_updatable_and_protected_are_disjoint(self):
        assert not TRANSACTION_UPDATABLE_FIELDS & TRANSACTION_PROTECTED_FIELDS

    @pytest.mark.parametrize('field', [
        'receipt_id', 'deleted_at', 'deleted_reason',
        'source_transaction_id', 'source_relationship',
        'id', 'created_at', 'upload_id', 'account_id',
    ])
    def test_lifecycle_and_link_fields_are_never_updatable(self, field):
        assert field not in TRANSACTION_UPDATABLE_FIELDS
        assert field in TRANSACTION_PROTECTED_FIELDS


# --------------------------------------------------------------------------- #
# add_transaction
# --------------------------------------------------------------------------- #
class TestAddTransaction:

    def test_returns_id_of_persisted_row(self, repo, upload_id, party_id, account_id, row):
        model = make_model(
            upload_id, party_id, account_id=account_id, amount=-42.50,
            is_credit=False, is_kids=True, is_one_off=True,
        )
        transaction_id = repo.add_transaction(model)
        assert transaction_id > 0

        saved = row(transaction_id)
        assert saved['amount'] == -42.50
        assert saved['description'] == 'TESCO STORES 1234'
        assert saved['cleaned_description'] == 'TESCO'
        assert saved['account_id'] == account_id
        assert saved['party_id'] == party_id
        assert saved['upload_id'] == upload_id
        assert saved['is_kids'] == 1
        assert saved['deleted_at'] is None

    def test_unknown_party_rejected(self, repo, upload_id):
        with pytest.raises(DatabaseError):
            repo.add_transaction(make_model(upload_id, 999))

    def test_unknown_upload_rejected(self, repo, party_id):
        with pytest.raises(DatabaseError):
            repo.add_transaction(make_model(999, party_id))


# --------------------------------------------------------------------------- #
# bulk inserts
# --------------------------------------------------------------------------- #
class TestBulkAddFromDataFrame:

    def test_inserts_rows_and_returns_ids(self, repo, upload_id, party_id):
        df = pd.DataFrame([
            {'transaction_date': '2024-01-15', 'amount': -10.0, 'description': 'A',
             'upload_id': upload_id, 'party_id': party_id},
            {'transaction_date': '2024-01-16', 'amount': -20.0, 'description': 'B',
             'upload_id': upload_id, 'party_id': party_id},
        ])
        ids = repo.bulk_add_transactions(df)

        assert len(ids) == 2
        assert {t['description'] for t in repo.get_transactions_with_hierarchy()} == {'A', 'B'}

    def test_missing_required_columns_rejected(self, repo):
        with pytest.raises(ValueError) as exc:
            repo.bulk_add_transactions(pd.DataFrame([{'amount': -1.0}]))
        assert 'Missing required columns' in str(exc.value)

    def test_optional_columns_get_defaults(self, repo, upload_id, party_id, row):
        df = pd.DataFrame([
            {'transaction_date': '2024-01-15', 'amount': -10.0, 'description': 'A',
             'upload_id': upload_id, 'party_id': party_id},
        ])
        saved = row(repo.bulk_add_transactions(df)[0])
        assert saved['cleaned_description'] is None
        assert saved['is_credit'] == 0
        assert saved['is_kids'] == 0
        assert saved['receipt_id'] is None

    def test_dates_normalised_to_iso(self, repo, upload_id, party_id, row):
        df = pd.DataFrame([
            {'transaction_date': '15/01/2024', 'amount': -10.0, 'description': 'A',
             'upload_id': upload_id, 'party_id': party_id},
        ])
        saved = row(repo.bulk_add_transactions(df)[0])
        assert saved['transaction_date'] == '2024-01-15'

    def test_batch_is_atomic(self, repo, upload_id, party_id):
        df = pd.DataFrame([
            {'transaction_date': '2024-01-15', 'amount': -10.0, 'description': 'A',
             'upload_id': upload_id, 'party_id': party_id},
            {'transaction_date': '2024-01-16', 'amount': -20.0, 'description': 'B',
             'upload_id': upload_id, 'party_id': 999},  # bad FK
        ])
        with pytest.raises(DatabaseError):
            repo.bulk_add_transactions(df)
        assert repo.get_transactions_with_hierarchy() == []


class TestBulkAddFromObjects:

    @LASTROWID_AFTER_EXECUTEMANY
    def test_inserts_rows_and_returns_ids(self, repo, upload_id, party_id):
        models = [
            make_model(upload_id, party_id, description='A', amount=-1.0),
            make_model(upload_id, party_id, description='B', amount=-2.0),
            make_model(upload_id, party_id, description='C', amount=-3.0),
        ]
        ids = repo.bulk_add_transactions_from_objects(models)

        assert len(ids) == 3
        assert {t['id'] for t in repo.get_transactions_with_hierarchy()} == set(ids)

    def test_empty_list_returns_empty(self, repo):
        assert repo.bulk_add_transactions_from_objects([]) == []

    def test_batch_is_atomic(self, repo, upload_id, party_id):
        # Passes today because the FK violation is raised before the
        # lastrowid bug above can bite.
        models = [
            make_model(upload_id, party_id, description='A'),
            make_model(upload_id, 999, description='B'),  # bad FK
        ]
        with pytest.raises(DatabaseError) as exc:
            repo.bulk_add_transactions_from_objects(models)
        assert 'FOREIGN KEY' in str(exc.value)
        assert repo.get_transactions_with_hierarchy() == []


# --------------------------------------------------------------------------- #
# get_transactions / get_transaction_by_id
# --------------------------------------------------------------------------- #
class TestGetTransactions:

    def test_empty_database(self, repo):
        assert repo.get_transactions() == []

    @MODEL_MISMATCH
    def test_returns_model_instances_with_context(
        self, repo, make_txn, account_id, test_hierarchy
    ):
        make_txn(account_id=account_id)
        transaction = repo.get_transactions()[0]

        assert isinstance(transaction, Transaction)
        assert transaction.account_name == 'Main Checking'
        assert transaction.related_party_name == 'Test Party'

    @MODEL_MISMATCH
    def test_ordered_by_date_descending(self, repo, make_txn):
        make_txn(transaction_date='2024-01-01')
        newest = make_txn(transaction_date='2024-03-01')
        assert repo.get_transactions()[0].id == newest

    @MODEL_MISMATCH
    def test_limit(self, repo, make_txn):
        for _ in range(3):
            make_txn()
        assert len(repo.get_transactions(limit=2)) == 2

    @MODEL_MISMATCH
    def test_excludes_soft_deleted_by_default(self, repo, make_txn, app_with_db, test_data):
        keep = make_txn()
        drop = make_txn()
        test_data.soft_delete_transaction(app_with_db, drop)
        assert [t.id for t in repo.get_transactions()] == [keep]

    @MODEL_MISMATCH
    def test_include_deleted(self, repo, make_txn, app_with_db, test_data):
        keep = make_txn()
        drop = make_txn()
        test_data.soft_delete_transaction(app_with_db, drop)
        assert {t.id for t in repo.get_transactions(include_deleted=True)} == {keep, drop}


class TestGetTransactionById:

    @MODEL_MISMATCH
    def test_found(self, repo, make_txn):
        transaction_id = make_txn()
        assert repo.get_transaction_by_id(transaction_id).id == transaction_id

    def test_missing_returns_none(self, repo):
        assert repo.get_transaction_by_id(999) is None

    def test_soft_deleted_hidden_by_default(self, repo, make_txn, app_with_db, test_data):
        transaction_id = make_txn()
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.get_transaction_by_id(transaction_id) is None

    @MODEL_MISMATCH
    def test_soft_deleted_visible_when_requested(
        self, repo, make_txn, app_with_db, test_data
    ):
        transaction_id = make_txn()
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        found = repo.get_transaction_by_id(transaction_id, include_deleted=True)
        assert found.id == transaction_id
        assert found.deleted_reason == 'user'


# --------------------------------------------------------------------------- #
# get_transactions_with_hierarchy
# --------------------------------------------------------------------------- #
class TestGetTransactionsWithHierarchy:

    def test_empty_database(self, repo):
        assert repo.get_transactions_with_hierarchy() == []

    def test_includes_full_hierarchy(self, repo, make_txn, account_id, test_hierarchy):
        make_txn(account_id=account_id)
        found = repo.get_transactions_with_hierarchy()[0]

        assert found['account_name'] == 'Main Checking'
        assert found['account_type'] == 'checking'
        assert found['party_name'] == 'Test Party'
        assert found['type_name'] == 'Test Type'
        assert found['sub_category_name'] == 'Test SubCategory'
        assert found['category_name'] == 'Test Category'
        assert found['category_id'] == test_hierarchy['category_id']

    def test_filter_by_date_range(self, repo, make_txn):
        make_txn(transaction_date='2024-01-01')
        middle = make_txn(transaction_date='2024-02-01')
        make_txn(transaction_date='2024-03-01')
        found = repo.get_transactions_with_hierarchy(
            start_date='2024-01-15', end_date='2024-02-15'
        )
        assert [t['id'] for t in found] == [middle]

    def test_filter_by_party_account_and_upload(
        self, repo, make_txn, account_id, party_id, upload_id
    ):
        transaction_id = make_txn(account_id=account_id)
        assert len(repo.get_transactions_with_hierarchy(party_id=party_id)) == 1
        assert len(repo.get_transactions_with_hierarchy(account_id=account_id)) == 1
        assert len(repo.get_transactions_with_hierarchy(upload_id=upload_id)) == 1
        assert repo.get_transactions_with_hierarchy(account_id=999) == []

    def test_filter_by_description_substring(self, repo, make_txn):
        match = make_txn(description='TESCO STORES', cleaned_description='TESCO')
        make_txn(description='ALDI', cleaned_description='ALDI')
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            description='TESCO')] == [match]
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            cleaned_description='TESC')] == [match]

    @pytest.mark.parametrize('flag', ['is_kids', 'is_one_off', 'is_credit'])
    def test_filter_by_boolean_flags(self, repo, make_txn, flag):
        flagged = make_txn(**{flag: 1})
        plain = make_txn()
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            **{flag: True})] == [flagged]
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            **{flag: False})] == [plain]

    def test_filter_by_hierarchy_levels(self, repo, make_txn, test_hierarchy):
        make_txn()
        for key, kwarg in [
            ('category_id', 'category_id'),
            ('subcategory_id', 'sub_category_id'),
            ('type_id', 'type_id'),
        ]:
            assert len(repo.get_transactions_with_hierarchy(
                **{kwarg: test_hierarchy[key]})) == 1
            assert repo.get_transactions_with_hierarchy(**{kwarg: 999}) == []

    def test_filter_by_has_receipt(self, repo, make_txn, app_with_db, test_data):
        from src.services.receipt_links import ReceiptLinkService

        linked = make_txn()
        unlinked_txn = make_txn()
        receipt_id = test_data.create_receipt(app_with_db)
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, linked)

        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            has_receipt=True)] == [linked]
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            has_receipt=False)] == [unlinked_txn]

    def test_receipt_columns_populated_when_linked(
        self, repo, make_txn, app_with_db, test_data
    ):
        from src.services.receipt_links import ReceiptLinkService

        transaction_id = make_txn()
        receipt_id = test_data.create_receipt(app_with_db, vendor='Tesco', amount=10.0)
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, transaction_id)

        found = repo.get_transactions_with_hierarchy()[0]
        assert found['receipt_id'] == receipt_id
        assert found['receipt_vendor'] == 'Tesco'
        assert found['receipt_amount'] == 10.0

    def test_limit_and_offset(self, repo, make_txn):
        for day in range(1, 4):
            make_txn(transaction_date=f'2024-01-0{day}')
        page1 = repo.get_transactions_with_hierarchy(limit=2)
        page2 = repo.get_transactions_with_hierarchy(limit=2, offset=2)
        assert len(page1) == 2 and len(page2) == 1
        assert not {t['id'] for t in page1} & {t['id'] for t in page2}

    def test_sort_by_amount_ascending(self, repo, make_txn):
        for amount in (-5.0, -50.0, -15.0):
            make_txn(amount=amount)
        amounts = [t['amount'] for t in repo.get_transactions_with_hierarchy(
            sort_by='amount', sort_dir='asc')]
        assert amounts == sorted(amounts)

    def test_defaults_to_date_descending(self, repo, make_txn):
        make_txn(transaction_date='2024-01-01')
        newest = make_txn(transaction_date='2024-03-01')
        assert repo.get_transactions_with_hierarchy()[0]['id'] == newest

    def test_unknown_sort_column_falls_back_to_default(self, repo, make_txn):
        make_txn(transaction_date='2024-01-01')
        newest = make_txn(transaction_date='2024-03-01')
        found = repo.get_transactions_with_hierarchy(sort_by='; DROP TABLE transactions')
        assert found[0]['id'] == newest

    def test_soft_delete_filters(self, repo, make_txn, app_with_db, test_data):
        live = make_txn()
        deleted = make_txn()
        test_data.soft_delete_transaction(app_with_db, deleted)

        assert [t['id'] for t in repo.get_transactions_with_hierarchy()] == [live]
        assert {t['id'] for t in repo.get_transactions_with_hierarchy(
            include_deleted=True)} == {live, deleted}
        assert [t['id'] for t in repo.get_transactions_with_hierarchy(
            deleted_only=True)] == [deleted]

    def test_deleted_only_takes_precedence_over_include_deleted(
        self, repo, make_txn, app_with_db, test_data
    ):
        make_txn()
        deleted = make_txn()
        test_data.soft_delete_transaction(app_with_db, deleted)
        found = repo.get_transactions_with_hierarchy(
            deleted_only=True, include_deleted=True
        )
        assert [t['id'] for t in found] == [deleted]

    def test_filter_by_deleted_reason(self, repo, make_txn, app_with_db, test_data):
        user_deleted = make_txn()
        cascade_deleted = make_txn()
        test_data.soft_delete_transaction(app_with_db, user_deleted, reason='user')
        test_data.soft_delete_transaction(app_with_db, cascade_deleted, reason='cascade')

        found = repo.get_transactions_with_hierarchy(
            deleted_only=True, deleted_reason='cascade'
        )
        assert [t['id'] for t in found] == [cascade_deleted]


class TestGetTransactionWithHierarchy:

    def test_found(self, repo, make_txn):
        transaction_id = make_txn()
        found = repo.get_transaction_with_hierarchy(transaction_id)
        assert found['id'] == transaction_id
        assert found['party_name'] == 'Test Party'

    def test_missing_returns_none(self, repo):
        assert repo.get_transaction_with_hierarchy(999) is None

    def test_soft_deleted_hidden_by_default(self, repo, make_txn, app_with_db, test_data):
        transaction_id = make_txn()
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.get_transaction_with_hierarchy(transaction_id) is None
        assert repo.get_transaction_with_hierarchy(
            transaction_id, include_deleted=True
        )['id'] == transaction_id


# --------------------------------------------------------------------------- #
# update_transaction
# --------------------------------------------------------------------------- #
class TestUpdateTransaction:

    def test_updates_allowlisted_fields(self, repo, make_txn):
        transaction_id = make_txn()
        updated = repo.update_transaction(
            transaction_id,
            amount=-99.99,
            description='NEW DESC',
            cleaned_description='NEW',
            is_kids=1,
            is_one_off=1,
            is_credit=1,
            transaction_date='2024-06-01',
        )
        assert updated['amount'] == -99.99
        assert updated['description'] == 'NEW DESC'
        assert updated['cleaned_description'] == 'NEW'
        assert updated['transaction_date'] == '2024-06-01'
        assert updated['is_kids'] == 1

    def test_update_party_moves_hierarchy(self, repo, make_txn, test_hierarchy):
        from src.database.repositories.categories import CategoryRepository

        other_party = CategoryRepository().add_party('Other Party', test_hierarchy['type_id'])
        updated = repo.update_transaction(make_txn(), party_id=other_party)
        assert updated['party_name'] == 'Other Party'

    def test_no_valid_fields_returns_current_row(self, repo, make_txn):
        transaction_id = make_txn()
        assert repo.update_transaction(transaction_id, bogus='x') == \
            repo.get_transaction_with_hierarchy(transaction_id)

    def test_missing_transaction_returns_none(self, repo):
        assert repo.update_transaction(999, amount=-1.0) is None

    def test_soft_deleted_is_not_updatable(self, repo, make_txn, app_with_db, test_data):
        transaction_id = make_txn()
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.update_transaction(transaction_id, amount=-1.0) is None

    def test_ignores_receipt_id(self, repo, make_txn, unlinked, row):
        transaction_id = make_txn()
        repo.update_transaction(transaction_id, receipt_id=unlinked)
        assert row(transaction_id)['receipt_id'] is None

    @pytest.mark.parametrize('field,value', [
        ('deleted_at', '2024-01-01 00:00:00.000'),
        ('deleted_reason', 'user'),
        ('source_transaction_id', 1),
        ('source_relationship', 'split'),
        ('account_id', 1),
        ('upload_id', 1),
    ])
    def test_ignores_protected_fields(self, repo, make_txn, row, field, value):
        transaction_id = make_txn()
        before = row(transaction_id)[field]
        repo.update_transaction(transaction_id, **{field: value})
        assert row(transaction_id)[field] == before

    def test_bad_party_rejected(self, repo, make_txn):
        with pytest.raises(DatabaseError):
            repo.update_transaction(make_txn(), party_id=999)


class TestBulkUpdateTransactions:

    def test_updates_every_listed_row(self, repo, make_txn):
        ids = [make_txn() for _ in range(3)]
        result = repo.bulk_update_transactions(ids, is_kids=1)

        assert result['updated_count'] == 3
        assert result['updated_ids'] == ids
        assert result['fields_updated'] == ['is_kids']
        assert all(repo.get_transaction_with_hierarchy(i)['is_kids'] == 1 for i in ids)

    def test_leaves_unlisted_rows_alone(self, repo, make_txn):
        target = make_txn()
        other = make_txn()
        repo.bulk_update_transactions([target], is_one_off=1)
        assert repo.get_transaction_with_hierarchy(other)['is_one_off'] == 0

    def test_empty_id_list(self, repo):
        assert repo.bulk_update_transactions([]) == {'updated_count': 0, 'updated_ids': []}

    def test_no_valid_fields(self, repo, make_txn):
        assert repo.bulk_update_transactions([make_txn()], bogus='x') == \
            {'updated_count': 0, 'updated_ids': []}

    def test_skips_soft_deleted(self, repo, make_txn, app_with_db, test_data):
        live = make_txn()
        deleted = make_txn()
        test_data.soft_delete_transaction(app_with_db, deleted)

        result = repo.bulk_update_transactions([live, deleted], is_kids=1)
        assert result['updated_count'] == 1

    def test_ignores_receipt_id(self, repo, make_txn, unlinked, row):
        transaction_id = make_txn()
        repo.bulk_update_transactions([transaction_id], receipt_id=unlinked)
        assert row(transaction_id)['receipt_id'] is None

    def test_unknown_ids_are_counted_out(self, repo, make_txn):
        live = make_txn()
        assert repo.bulk_update_transactions([live, 999], is_kids=1)['updated_count'] == 1


# --------------------------------------------------------------------------- #
# soft delete / restore
# --------------------------------------------------------------------------- #
class TestDeleteTransaction:

    def test_soft_deletes_with_user_reason(self, repo, make_txn, row):
        transaction_id = make_txn()
        result = repo.delete_transaction(transaction_id)

        assert result == {
            'deleted': True, 'transaction_id': transaction_id, 'cascaded_ids': []
        }
        saved = row(transaction_id)
        assert saved['deleted_at'] is not None
        assert saved['deleted_reason'] == 'user'

    def test_missing_transaction(self, repo):
        assert repo.delete_transaction(999)['deleted'] is False

    def test_already_deleted_is_a_noop(self, repo, make_txn):
        transaction_id = make_txn()
        repo.delete_transaction(transaction_id)
        assert repo.delete_transaction(transaction_id)['deleted'] is False

    def test_cascades_to_generated_children(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')

        result = repo.delete_transaction(parent)

        assert result['cascaded_ids'] == [child]
        assert row(child)['deleted_reason'] == 'cascade'

    def test_does_not_cascade_to_split_children(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'split')

        result = repo.delete_transaction(parent)

        assert result['cascaded_ids'] == []
        assert row(child)['deleted_at'] is None

    def test_keeps_user_reason_on_already_deleted_child(
        self, repo, make_txn, link_child, row
    ):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')

        repo.delete_transaction(child)
        repo.delete_transaction(parent)

        assert row(child)['deleted_reason'] == 'user'

    def test_split_child_cannot_be_deleted_alone(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'split')

        with pytest.raises(TransactionRuleError) as exc:
            repo.delete_transaction(child)
        assert f'Unsplit transaction {parent}' in str(exc.value)
        assert row(child)['deleted_at'] is None


class TestBulkDeleteTransactions:

    def test_deletes_all_listed(self, repo, make_txn, row):
        ids = [make_txn() for _ in range(3)]
        result = repo.bulk_delete_transactions(ids)

        assert result['deleted_count'] == 3
        assert sorted(result['deleted_ids']) == sorted(ids)
        assert result['skipped_ids'] == []
        assert all(row(i)['deleted_reason'] == 'user' for i in ids)

    def test_empty_list(self, repo):
        assert repo.bulk_delete_transactions([]) == {
            'deleted_count': 0, 'deleted_ids': [], 'cascaded_ids': [], 'skipped_ids': []
        }

    def test_duplicates_collapsed(self, repo, make_txn):
        transaction_id = make_txn()
        result = repo.bulk_delete_transactions([transaction_id, transaction_id])
        assert result['deleted_count'] == 1

    def test_missing_and_already_deleted_are_skipped(self, repo, make_txn):
        live = make_txn()
        already = make_txn()
        repo.delete_transaction(already)

        result = repo.bulk_delete_transactions([live, already, 999])
        assert result['deleted_ids'] == [live]
        assert sorted(result['skipped_ids']) == sorted([already, 999])

    def test_cascades_to_generated_children(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')

        result = repo.bulk_delete_transactions([parent])

        assert result['cascaded_ids'] == [child]
        assert row(child)['deleted_reason'] == 'cascade'

    def test_explicitly_selected_child_is_recorded_as_user(
        self, repo, make_txn, link_child, row
    ):
        """Ordering matters: a child the user selected must survive a later restore."""
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')

        result = repo.bulk_delete_transactions([parent, child])

        assert result['cascaded_ids'] == []
        assert row(child)['deleted_reason'] == 'user'

    def test_split_child_rejects_whole_batch(self, repo, make_txn, link_child, row):
        parent = make_txn()
        split_child = make_txn()
        link_child(split_child, parent, 'split')
        innocent = make_txn()

        with pytest.raises(TransactionRuleError) as exc:
            repo.bulk_delete_transactions([innocent, split_child])
        assert 'Unsplit their source transactions first' in str(exc.value)
        assert row(innocent)['deleted_at'] is None

    def test_chunking_handles_more_ids_than_the_variable_limit(self, repo, make_txn):
        ids = [make_txn() for _ in range(5)]
        repo._MAX_SQL_VARIABLES = 2  # force multiple chunks
        try:
            result = repo.bulk_delete_transactions(ids)
        finally:
            del repo._MAX_SQL_VARIABLES
        assert result['deleted_count'] == 5


class TestRestoreTransaction:

    def test_restores_user_deleted(self, repo, make_txn, row):
        transaction_id = make_txn()
        repo.delete_transaction(transaction_id)

        result = repo.restore_transaction(transaction_id)

        assert result == {
            'restored': True, 'transaction_id': transaction_id, 'restored_ids': []
        }
        saved = row(transaction_id)
        assert saved['deleted_at'] is None
        assert saved['deleted_reason'] is None

    def test_missing_transaction(self, repo):
        assert repo.restore_transaction(999)['restored'] is False

    def test_live_transaction_is_a_noop(self, repo, make_txn):
        assert repo.restore_transaction(make_txn())['restored'] is False

    def test_restores_cascaded_children(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')
        repo.delete_transaction(parent)

        result = repo.restore_transaction(parent)

        assert result['restored_ids'] == [child]
        assert row(child)['deleted_at'] is None

    def test_leaves_user_deleted_children_deleted(self, repo, make_txn, link_child, row):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')
        repo.delete_transaction(child)
        repo.delete_transaction(parent)

        result = repo.restore_transaction(parent)

        assert result['restored_ids'] == []
        assert row(child)['deleted_at'] is not None

    @pytest.mark.parametrize('reason', ['cascade', 'superseded', 'unsplit'])
    def test_non_user_reasons_are_rejected(
        self, repo, make_txn, app_with_db, test_data, row, reason
    ):
        transaction_id = make_txn()
        test_data.soft_delete_transaction(app_with_db, transaction_id, reason=reason)

        with pytest.raises(TransactionRuleError) as exc:
            repo.restore_transaction(transaction_id)
        assert f'Cannot restore transaction {transaction_id}' in str(exc.value)
        assert row(transaction_id)['deleted_at'] is not None

    def test_child_cannot_outlive_a_deleted_parent(
        self, repo, make_txn, link_child, app_with_db, test_data
    ):
        parent = make_txn()
        child = make_txn()
        link_child(child, parent, 'generated')
        # Child deleted by the user first, then the parent - so the child
        # carries reason='user' and is restorable on its own terms.
        repo.delete_transaction(child)
        repo.delete_transaction(parent)

        with pytest.raises(TransactionRuleError) as exc:
            repo.restore_transaction(child)
        assert f'source transaction {parent} is deleted' in str(exc.value)


# --------------------------------------------------------------------------- #
# matching queries
# --------------------------------------------------------------------------- #
class TestFindReceiptMatchCandidates:

    @BROKEN_SQL
    def test_matches_within_tolerances(self, repo, make_txn):
        exact = make_txn(amount=-25.99, transaction_date='2024-01-15')
        make_txn(amount=-99.00, transaction_date='2024-01-15')
        make_txn(amount=-25.99, transaction_date='2024-06-01')

        found = repo.find_receipt_match_candidates(
            amount=-25.99, transaction_date='2024-01-15'
        )
        assert [t.id for t in found] == [exact]

    @BROKEN_SQL
    def test_amount_tolerance_is_inclusive(self, repo, make_txn):
        near = make_txn(amount=-26.00, transaction_date='2024-01-15')
        found = repo.find_receipt_match_candidates(
            amount=-25.99, transaction_date='2024-01-15', amount_tolerance=0.01
        )
        assert [t.id for t in found] == [near]

    @BROKEN_SQL
    def test_date_tolerance(self, repo, make_txn):
        make_txn(amount=-25.99, transaction_date='2024-01-25')
        assert repo.find_receipt_match_candidates(
            amount=-25.99, transaction_date='2024-01-15', date_tolerance_days=7
        ) == []
        assert len(repo.find_receipt_match_candidates(
            amount=-25.99, transaction_date='2024-01-15', date_tolerance_days=30
        )) == 1

    @BROKEN_SQL
    def test_ordered_by_date_then_amount_proximity(self, repo, make_txn):
        far = make_txn(amount=-25.99, transaction_date='2024-01-18')
        near = make_txn(amount=-26.00, transaction_date='2024-01-15')

        found = repo.find_receipt_match_candidates(
            amount=-25.99, transaction_date='2024-01-15', amount_tolerance=0.05
        )
        assert [t.id for t in found] == [near, far]

    @BROKEN_SQL
    def test_excludes_already_linked_by_default(
        self, repo, make_txn, app_with_db, test_data
    ):
        from src.services.receipt_links import ReceiptLinkService

        linked = make_txn(amount=-25.99, transaction_date='2024-01-15')
        receipt_id = test_data.create_receipt(app_with_db)
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, linked)

        assert repo.find_receipt_match_candidates(-25.99, '2024-01-15') == []
        assert len(repo.find_receipt_match_candidates(
            -25.99, '2024-01-15', include_matched=True
        )) == 1

    @BROKEN_SQL
    def test_excludes_soft_deleted(self, repo, make_txn, app_with_db, test_data):
        transaction_id = make_txn(amount=-25.99, transaction_date='2024-01-15')
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.find_receipt_match_candidates(-25.99, '2024-01-15') == []

    @BROKEN_SQL
    def test_no_candidates(self, repo):
        assert repo.find_receipt_match_candidates(-1.00, '2024-01-15') == []


class TestFindMatchingTransactions:

    def test_requires_at_least_one_parameter(self, repo):
        with pytest.raises(ValueError) as exc:
            repo.find_matching_transactions()
        assert 'At least one search parameter' in str(exc.value)

    def test_match_by_amount(self, repo, make_txn):
        match = make_txn(amount=-25.99)
        make_txn(amount=-1.00)
        assert [t['id'] for t in repo.find_matching_transactions(amount=-25.99)] == [match]

    def test_match_by_date(self, repo, make_txn):
        match = make_txn(transaction_date='2024-01-15')
        make_txn(transaction_date='2024-06-01')
        found = repo.find_matching_transactions(transaction_date='2024-01-15')
        assert [t['id'] for t in found] == [match]

    def test_match_by_party_name_is_case_insensitive(self, repo, make_txn):
        match = make_txn()
        found = repo.find_matching_transactions(party_name='test party')
        assert [t['id'] for t in found] == [match]

    def test_match_by_cleaned_description(self, repo, make_txn):
        match = make_txn(cleaned_description='TESCO METRO')
        make_txn(cleaned_description='ALDI')
        found = repo.find_matching_transactions(party_name='tesco')
        assert [t['id'] for t in found] == [match]

    def test_include_matched_false_excludes_linked(
        self, repo, make_txn, app_with_db, test_data
    ):
        from src.services.receipt_links import ReceiptLinkService

        linked = make_txn(amount=-25.99)
        receipt_id = test_data.create_receipt(app_with_db)
        with app_with_db.app_context():
            ReceiptLinkService().link(receipt_id, linked)

        assert len(repo.find_matching_transactions(amount=-25.99)) == 1
        assert repo.find_matching_transactions(amount=-25.99, include_matched=False) == []

    def test_excludes_soft_deleted(self, repo, make_txn, app_with_db, test_data):
        transaction_id = make_txn(amount=-25.99)
        test_data.soft_delete_transaction(app_with_db, transaction_id)
        assert repo.find_matching_transactions(amount=-25.99) == []

    def test_limit(self, repo, make_txn):
        for _ in range(3):
            make_txn(amount=-25.99)
        assert len(repo.find_matching_transactions(amount=-25.99, limit=2)) == 2

    def test_returns_hierarchy_fields(self, repo, make_txn):
        make_txn(amount=-25.99)
        found = repo.find_matching_transactions(amount=-25.99)[0]
        assert found['party_name'] == 'Test Party'
        assert found['category_name'] == 'Test Category'


# --------------------------------------------------------------------------- #
# link_receipt_to_transaction (deprecated delegator)
# --------------------------------------------------------------------------- #
class TestLinkReceiptToTransaction:

    def test_delegates_to_link_service(self, repo, make_txn, unlinked, row):
        transaction_id = make_txn()
        result = repo.link_receipt_to_transaction(transaction_id, unlinked)

        assert result['receipt_id'] == unlinked
        assert row(transaction_id)['receipt_id'] == unlinked


# --------------------------------------------------------------------------- #
# export_data
# --------------------------------------------------------------------------- #
class TestExportData:

    def test_empty_database(self, repo):
        assert repo.export_data() == []

    def test_returns_denormalised_rows(self, repo, make_txn, account_id):
        make_txn(account_id=account_id, description='TESCO STORES')
        exported = repo.export_data()

        assert len(exported) == 1
        assert exported[0]['account_name'] == 'Main Checking'
        assert exported[0]['party'] == 'Test Party'
        assert exported[0]['type'] == 'Test Type'
        assert exported[0]['sub_category'] == 'Test SubCategory'
        assert exported[0]['category'] == 'Test Category'

    def test_excludes_soft_deleted(self, repo, make_txn, app_with_db, test_data):
        live = make_txn()
        deleted = make_txn()
        test_data.soft_delete_transaction(app_with_db, deleted)
        assert [t['id'] for t in repo.export_data()] == [live]

    def test_ordered_by_date_ascending(self, repo, make_txn):
        make_txn(transaction_date='2024-03-01')
        make_txn(transaction_date='2024-01-01')
        dates = [t['transaction_date'] for t in repo.export_data()]
        assert dates == sorted(dates)


# --------------------------------------------------------------------------- #
# error wrapping
# --------------------------------------------------------------------------- #
class TestErrorWrapping:

    @pytest.fixture
    def broken_repo(self, repo):
        class Boom:
            def get_connection(self):
                raise RuntimeError('connection exploded')

            def transaction(self):
                raise RuntimeError('connection exploded')

        repo.db = Boom()
        return repo

    @pytest.mark.parametrize('call', [
        lambda r: r.add_transaction(make_model(1, 1)),
        lambda r: r.get_transactions(),
        lambda r: r.get_transaction_by_id(1),
        lambda r: r.get_transactions_with_hierarchy(),
        lambda r: r.get_transaction_with_hierarchy(1),
        lambda r: r.update_transaction(1, amount=-1.0),
        lambda r: r.bulk_update_transactions([1], amount=-1.0),
        lambda r: r.delete_transaction(1),
        lambda r: r.bulk_delete_transactions([1]),
        lambda r: r.restore_transaction(1),
        lambda r: r.find_receipt_match_candidates(-1.0, '2024-01-15'),
        lambda r: r.find_matching_transactions(amount=-1.0),
        lambda r: r.export_data(),
    ])
    def test_db_failures_surface_as_database_error(self, broken_repo, call):
        with pytest.raises(DatabaseError):
            call(broken_repo)
