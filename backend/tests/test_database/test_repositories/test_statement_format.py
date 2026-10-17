"""
StatementFormatRepository tests against a real migrated SQLite database.

No mocking of the database layer: a repository's job is SQL, so the tests
run SQL. The only patched tests are the DatabaseError-wrapping checks.
"""
import json

import pytest

from src.database.errors import DatabaseError, RecordNotFound
from src.database.repositories.statement_format import StatementFormatRepository


@pytest.fixture
def repo(app_with_db):
    with app_with_db.app_context():
        yield StatementFormatRepository()


@pytest.fixture
def config():
    """A config dict of roughly the shape StatementConfig.to_dict() produces."""
    return {
        'date_column': 'Transaction Date',
        'amount_column': 'Amount',
        'description_column': 'Description',
        'date_format': '%d/%m/%Y',
        'skip_rows': 1,
        'credit_is_positive': True,
    }


@pytest.fixture
def chase(repo, config):
    return repo.add_format('Chase', 'checking', config)


# --------------------------------------------------------------------------- #
# add_format
# --------------------------------------------------------------------------- #
class TestAddFormat:

    def test_returns_persisted_record(self, repo, config):
        fmt = repo.add_format('Chase', 'checking', config)

        assert fmt['id'] > 0
        assert fmt['bank_name'] == 'Chase'
        assert fmt['account_type'] == 'checking'
        assert fmt['config_json'] == config
        assert fmt['created_at'] is not None
        assert fmt['updated_at'] is not None

    def test_round_trips_through_get(self, repo, config):
        fmt = repo.add_format('Chase', 'checking', config)
        assert repo.get_format_by_id(fmt['id']) == fmt

    def test_config_stored_as_json_text(self, repo, config, db_manager):
        fmt = repo.add_format('Chase', 'checking', config)
        with db_manager.get_connection() as conn:
            raw = conn.execute(
                "SELECT config_json FROM statement_formats WHERE id = ?", (fmt['id'],)
            ).fetchone()[0]
        assert isinstance(raw, str)
        assert json.loads(raw) == config

    def test_empty_config_is_allowed(self, repo):
        fmt = repo.add_format('Chase', 'checking', {})
        # An empty dict serializes to '{}', which is falsy on read-back,
        # so it comes back as None rather than {}.
        assert fmt['config_json'] in ({}, None)

    def test_nested_config_round_trips(self, repo):
        nested = {'columns': {'date': 'A', 'amount': 'B'}, 'skip': [1, 2, 3]}
        fmt = repo.add_format('Chase', 'checking', nested)
        assert repo.get_format_by_id(fmt['id'])['config_json'] == nested

    def test_ids_increment(self, repo, config):
        a = repo.add_format('Chase', 'checking', config)
        b = repo.add_format('Chase', 'savings', config)
        assert b['id'] > a['id']

    def test_duplicate_bank_and_type_rejected(self, repo, config, chase):
        with pytest.raises(DatabaseError) as exc:
            repo.add_format('Chase', 'checking', config)
        assert 'already exists' in str(exc.value)

    def test_same_bank_different_type_allowed(self, repo, config, chase):
        other = repo.add_format('Chase', 'credit_card', config)
        assert other['id'] != chase['id']

    def test_same_type_different_bank_allowed(self, repo, config, chase):
        other = repo.add_format('Revolut', 'checking', config)
        assert other['id'] != chase['id']

    def test_unserializable_config_rejected(self, repo):
        with pytest.raises(DatabaseError) as exc:
            repo.add_format('Chase', 'checking', {'fn': lambda x: x})
        assert 'Invalid config_json' in str(exc.value)

    def test_unserializable_config_writes_nothing(self, repo):
        with pytest.raises(DatabaseError):
            repo.add_format('Chase', 'checking', {'fn': object()})
        assert repo.count_formats() == 0

    def test_null_bank_name_rejected(self, repo, config):
        with pytest.raises(DatabaseError):
            repo.add_format(None, 'checking', config)


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #
class TestGetFormatById:

    def test_found(self, repo, chase, config):
        fmt = repo.get_format_by_id(chase['id'])
        assert fmt['id'] == chase['id']
        assert fmt['config_json'] == config

    def test_missing_raises_record_not_found(self, repo):
        with pytest.raises(RecordNotFound) as exc:
            repo.get_format_by_id(999)
        assert exc.value.entity == 'StatementFormat'
        assert exc.value.criteria == {'id': 999}

    def test_record_not_found_is_a_database_error(self, repo):
        """Callers catching DatabaseError broadly must still see not-found."""
        with pytest.raises(DatabaseError):
            repo.get_format_by_id(999)


class TestGetFormatByBankAndType:

    def test_found(self, repo, chase):
        assert repo.get_format_by_bank_and_type('Chase', 'checking')['id'] == chase['id']

    def test_missing_returns_none(self, repo, chase):
        assert repo.get_format_by_bank_and_type('Chase', 'savings') is None
        assert repo.get_format_by_bank_and_type('Nope', 'checking') is None

    def test_empty_table_returns_none(self, repo):
        assert repo.get_format_by_bank_and_type('Chase', 'checking') is None

    def test_match_is_case_sensitive(self, repo, chase):
        assert repo.get_format_by_bank_and_type('chase', 'checking') is None


class TestGetAllFormats:

    def test_empty_table(self, repo):
        assert repo.get_all_formats() == []

    def test_returns_every_format(self, repo, config):
        created = {
            repo.add_format(bank, account_type, config)['id']
            for bank, account_type in [
                ('Chase', 'checking'), ('Chase', 'savings'), ('Revolut', 'checking')
            ]
        }
        assert {f['id'] for f in repo.get_all_formats()} == created

    def test_ordered_by_bank_then_account_type(self, repo, config):
        for bank, account_type in [
            ('Revolut', 'checking'),
            ('Chase', 'savings'),
            ('Chase', 'checking'),
        ]:
            repo.add_format(bank, account_type, config)

        assert [(f['bank_name'], f['account_type']) for f in repo.get_all_formats()] == [
            ('Chase', 'checking'), ('Chase', 'savings'), ('Revolut', 'checking')
        ]

    def test_config_deserialized_on_every_row(self, repo, config):
        repo.add_format('Chase', 'checking', config)
        repo.add_format('Revolut', 'checking', config)
        assert all(f['config_json'] == config for f in repo.get_all_formats())


# --------------------------------------------------------------------------- #
# malformed config_json
# --------------------------------------------------------------------------- #
class TestMalformedConfig:
    """A corrupt row must not take down a whole listing."""

    @pytest.fixture
    def corrupt(self, repo, chase, db_manager):
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE statement_formats SET config_json = ? WHERE id = ?",
                ('not json{', chase['id']),
            )
        return chase['id']

    def test_get_by_id_returns_none_config(self, repo, corrupt):
        fmt = repo.get_format_by_id(corrupt)
        assert fmt['config_json'] is None
        assert fmt['bank_name'] == 'Chase'  # the rest of the row survives

    def test_get_by_bank_and_type_returns_none_config(self, repo, corrupt):
        assert repo.get_format_by_bank_and_type('Chase', 'checking')['config_json'] is None

    def test_listing_still_includes_the_bad_row(self, repo, corrupt, config):
        repo.add_format('Revolut', 'checking', config)
        formats = {f['bank_name']: f for f in repo.get_all_formats()}
        assert formats['Chase']['config_json'] is None
        assert formats['Revolut']['config_json'] == config

    def test_update_can_repair_the_row(self, repo, corrupt, config):
        assert repo.update_format(corrupt, config_json=config)['config_json'] == config


# --------------------------------------------------------------------------- #
# update_format
# --------------------------------------------------------------------------- #
class TestUpdateFormat:

    def test_update_bank_name_only(self, repo, chase, config):
        updated = repo.update_format(chase['id'], bank_name='Chase UK')
        assert updated['bank_name'] == 'Chase UK'
        assert updated['account_type'] == 'checking'
        assert updated['config_json'] == config

    def test_update_account_type_only(self, repo, chase):
        updated = repo.update_format(chase['id'], account_type='savings')
        assert updated['account_type'] == 'savings'
        assert updated['bank_name'] == 'Chase'

    def test_update_config_replaces_wholesale(self, repo, chase):
        replacement = {'date_column': 'Date'}
        updated = repo.update_format(chase['id'], config_json=replacement)
        assert updated['config_json'] == replacement  # not merged

    def test_update_all_fields(self, repo, chase):
        updated = repo.update_format(
            chase['id'],
            bank_name='Revolut',
            account_type='credit_card',
            config_json={'x': 1},
        )
        assert (updated['bank_name'], updated['account_type']) == ('Revolut', 'credit_card')
        assert updated['config_json'] == {'x': 1}

    def test_update_persists(self, repo, chase):
        repo.update_format(chase['id'], bank_name='Persisted')
        assert repo.get_format_by_id(chase['id'])['bank_name'] == 'Persisted'

    def test_no_fields_returns_current_record(self, repo, chase):
        assert repo.update_format(chase['id']) == repo.get_format_by_id(chase['id'])

    def test_no_fields_does_not_bump_updated_at(self, repo, chase):
        before = repo.get_format_by_id(chase['id'])['updated_at']
        repo.update_format(chase['id'])
        assert repo.get_format_by_id(chase['id'])['updated_at'] == before

    def test_update_bumps_updated_at(self, repo, chase):
        before = repo.get_format_by_id(chase['id'])['updated_at']
        updated = repo.update_format(chase['id'], bank_name='Chase UK')
        assert updated['updated_at'] > before

    def test_update_leaves_created_at_alone(self, repo, chase):
        before = repo.get_format_by_id(chase['id'])['created_at']
        repo.update_format(chase['id'], bank_name='Chase UK')
        assert repo.get_format_by_id(chase['id'])['created_at'] == before

    def test_missing_format_returns_none(self, repo):
        assert repo.update_format(999, bank_name='Nope') is None

    def test_no_fields_on_missing_format_raises_not_found(self, repo):
        """The no-op path delegates to get_format_by_id, which raises."""
        with pytest.raises(RecordNotFound):
            repo.update_format(999)

    def test_conflicting_pair_rejected(self, repo, chase, config):
        other = repo.add_format('Revolut', 'checking', config)
        with pytest.raises(DatabaseError) as exc:
            repo.update_format(other['id'], bank_name='Chase')
        assert 'already exists' in str(exc.value)

    def test_conflicting_update_leaves_row_unchanged(self, repo, chase, config):
        other = repo.add_format('Revolut', 'checking', config)
        with pytest.raises(DatabaseError):
            repo.update_format(other['id'], bank_name='Chase')
        assert repo.get_format_by_id(other['id'])['bank_name'] == 'Revolut'

    def test_unserializable_config_rejected(self, repo, chase):
        with pytest.raises(DatabaseError) as exc:
            repo.update_format(chase['id'], config_json={'fn': object()})
        assert 'Invalid config_json' in str(exc.value)

    def test_unserializable_config_leaves_row_unchanged(self, repo, chase, config):
        with pytest.raises(DatabaseError):
            repo.update_format(chase['id'], bank_name='Chase UK',
                               config_json={'fn': object()})
        unchanged = repo.get_format_by_id(chase['id'])
        assert unchanged['bank_name'] == 'Chase'
        assert unchanged['config_json'] == config


# --------------------------------------------------------------------------- #
# delete_format
# --------------------------------------------------------------------------- #
class TestDeleteFormat:

    def test_delete_returns_true(self, repo, chase):
        assert repo.delete_format(chase['id']) is True
        with pytest.raises(RecordNotFound):
            repo.get_format_by_id(chase['id'])

    def test_delete_missing_returns_false(self, repo):
        assert repo.delete_format(999) is False

    def test_delete_is_idempotent_after_the_first_call(self, repo, chase):
        assert repo.delete_format(chase['id']) is True
        assert repo.delete_format(chase['id']) is False

    def test_only_deletes_the_target(self, repo, chase, config):
        other = repo.add_format('Revolut', 'checking', config)
        repo.delete_format(chase['id'])
        assert [f['id'] for f in repo.get_all_formats()] == [other['id']]

    def test_delete_does_not_check_accounts_referencing_it(
        self, repo, chase, db_manager
    ):
        """accounts.statement_format is a free-form string, not an FK, so a
        format in use can be deleted. Documents current behaviour."""
        with db_manager.transaction() as conn:
            conn.execute(
                "INSERT INTO accounts (account_name, account_type, statement_format) "
                "VALUES (?, ?, ?)",
                ('Main Checking', 'checking', str(chase['id'])),
            )
        assert repo.delete_format(chase['id']) is True


# --------------------------------------------------------------------------- #
# count_formats
# --------------------------------------------------------------------------- #
class TestCountFormats:

    def test_empty_table(self, repo):
        assert repo.count_formats() == 0

    def test_counts_rows(self, repo, config):
        for bank in ('Chase', 'Revolut', 'AIB'):
            repo.add_format(bank, 'checking', config)
        assert repo.count_formats() == 3

    def test_reflects_deletes(self, repo, chase):
        repo.delete_format(chase['id'])
        assert repo.count_formats() == 0


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
        lambda r: r.add_format('Chase', 'checking', {}),
        lambda r: r.get_format_by_id(1),
        lambda r: r.get_format_by_bank_and_type('Chase', 'checking'),
        lambda r: r.get_all_formats(),
        lambda r: r.update_format(1, bank_name='x'),
        lambda r: r.delete_format(1),
        lambda r: r.count_formats(),
    ])
    def test_db_failures_surface_as_database_error(self, broken_repo, call):
        with pytest.raises(DatabaseError):
            call(broken_repo)

    def test_not_found_is_not_masked_as_a_generic_failure(self, repo):
        """get_format_by_id re-raises RecordNotFound rather than wrapping it."""
        with pytest.raises(RecordNotFound):
            repo.get_format_by_id(999)