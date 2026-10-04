"""
AccountRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched test is the DatabaseError-wrapping check.
"""
import pytest

from src.database.errors import DatabaseError
from src.database.repositories.accounts import AccountRepository


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield AccountRepository()


@pytest.fixture
def checking(repo):
    return repo.add_account(account_name='Main Checking', account_type='checking')


# --------------------------------------------------------------------------- #
# add_account
# --------------------------------------------------------------------------- #
class TestAddAccount:

    def test_returns_persisted_dict(self, repo):
        acct = repo.add_account(account_name='Test Checking', account_type='checking')
        assert acct['id'] > 0
        assert acct['account_name'] == 'Test Checking'
        assert acct['account_type'] == 'checking'
        assert repo.get_account_by_id(acct['id']) == acct

    def test_ids_increment(self, repo):
        a = repo.add_account(account_name='A', account_type='checking')
        b = repo.add_account(account_name='B', account_type='savings')
        assert b['id'] > a['id']

    @pytest.mark.xfail(reason='No UNIQUE constraint on accounts.account_name yet - backlog', strict=True)
    def test_duplicate_name_rejected(self, repo, checking):
        with pytest.raises(DatabaseError):
            repo.add_account(account_name='Main Checking', account_type='checking')


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
class TestReads:

    def test_get_by_id_found(self, repo, checking):
        assert repo.get_account_by_id(checking['id']) == checking

    def test_get_by_id_missing(self, repo):
        assert repo.get_account_by_id(999) is None

    def test_get_by_name_found(self, repo, checking):
        assert repo.get_account_by_name('Main Checking')['id'] == checking['id']

    def test_get_by_name_missing(self, repo):
        assert repo.get_account_by_name('Nope') is None

    def test_get_all_empty(self, repo):
        assert repo.get_all_accounts() == []

    def test_get_all_returns_every_account(self, repo):
        created = {
            repo.add_account(account_name=n, account_type=t)['id']
            for n, t in [('Checking', 'checking'), ('Savings', 'savings'), ('Card', 'credit_card')]
        }
        assert {a['id'] for a in repo.get_all_accounts()} == created

    def test_get_by_type(self, repo):
        c1 = repo.add_account(account_name='Main', account_type='checking')
        c2 = repo.add_account(account_name='Joint', account_type='checking')
        repo.add_account(account_name='ISA', account_type='savings')
        assert {a['id'] for a in repo.get_accounts_by_type('checking')} == {c1['id'], c2['id']}

    def test_get_by_type_none_match(self, repo, checking):
        assert repo.get_accounts_by_type('mortgage') == []

    def test_distinct_types_sorted(self, repo):
        for i, t in enumerate(['savings', 'checking', 'credit_card', 'checking']):
            repo.add_account(account_name=f'A{i}', account_type=t)
        assert repo.get_distinct_account_types() == ['checking', 'credit_card', 'savings']

    def test_distinct_types_empty(self, repo):
        assert repo.get_distinct_account_types() == []


# --------------------------------------------------------------------------- #
# update_account
# --------------------------------------------------------------------------- #
class TestUpdateAccount:

    def test_update_name_only(self, repo, checking):
        updated = repo.update_account(checking['id'], account_name='Renamed')
        assert updated['account_name'] == 'Renamed'
        assert updated['account_type'] == 'checking'

    def test_update_type_only(self, repo, checking):
        updated = repo.update_account(checking['id'], account_type='savings')
        assert updated['account_type'] == 'savings'
        assert updated['account_name'] == 'Main Checking'

    def test_update_both(self, repo, checking):
        updated = repo.update_account(checking['id'], account_name='X', account_type='savings')
        assert (updated['account_name'], updated['account_type']) == ('X', 'savings')

    def test_update_no_fields_returns_current(self, repo, checking):
        assert repo.update_account(checking['id']) == checking

    def test_update_missing_returns_none(self, repo):
        assert repo.update_account(999, account_name='X') is None

    def test_update_persists(self, repo, checking):
        repo.update_account(checking['id'], account_name='Persisted')
        assert repo.get_account_by_id(checking['id'])['account_name'] == 'Persisted'


# --------------------------------------------------------------------------- #
# delete_account / transaction count
# --------------------------------------------------------------------------- #
class TestDeleteAccount:

    def test_delete_unused_account(self, repo, checking):
        assert repo.delete_account(checking['id']) is True
        assert repo.get_account_by_id(checking['id']) is None

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_account(999) is False

    def test_delete_with_transactions_is_rejected(
        self, repo, checking, app_with_db, test_data, test_hierarchy
    ):
        upload_id = test_data.create_upload(app_with_db)
        for _ in range(2):
            test_data.create_transaction(
                app_with_db, upload_id, test_hierarchy['party_id'], account_id=checking['id']
            )

        assert repo.get_account_transaction_count(checking['id']) == 2
        with pytest.raises(DatabaseError) as exc:
            repo.delete_account(checking['id'])
        assert 'Cannot delete account' in str(exc.value)
        assert '2 associated transaction(s)' in str(exc.value)
        assert repo.get_account_by_id(checking['id']) is not None

    def test_transaction_count_zero(self, repo, checking):
        assert repo.get_account_transaction_count(checking['id']) == 0

    def test_transaction_count_unknown_account(self, repo):
        assert repo.get_account_transaction_count(999) == 0


# --------------------------------------------------------------------------- #
# error wrapping - one test is enough to prove the pattern
# --------------------------------------------------------------------------- #
class TestErrorWrapping:

    def test_db_failures_surface_as_database_error(self, repo, monkeypatch):
        class Boom:
            def get_connection(self):
                raise RuntimeError('connection exploded')
            def transaction(self):
                raise RuntimeError('connection exploded')

        # After the lazy-db refactor, `db` is a property; patch the resolver
        # the repository module imports. AccountRepository
        # inherits BaseRepository (patch src.database.repositories.base.get_manager).
        monkeypatch.setattr('src.database.repositories.base.get_manager', lambda: Boom())

        with pytest.raises(DatabaseError) as exc:
            repo.get_all_accounts()
        assert 'Failed to get' in str(exc.value) or 'account' in str(exc.value).lower()