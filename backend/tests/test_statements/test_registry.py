"""
Tests for src/statements/registry.py.

The registry's three dependencies (repository, built-in configs, custom
processors) are all injectable, so most tests run against in-memory fakes with
no database. One class at the end wires up the real
`StatementFormatRepository` against the test database to prove the two agree.
"""
import pytest

from src.api.utils.errors import AppError, ErrorCode
from src.database.errors import RecordNotFound
from src.statements.base import (
    AmountConfig,
    ConfigurableStatementProcessor,
    DateConfig,
    StatementConfig,
    StatementProcessor,
)
from src.statements.registry import (
    FormatHandle,
    StatementFormatRegistry,
    get_processor,
)

EMPTY_INJECTION_IGNORED = pytest.mark.xfail(
    reason="__init__ uses `or` for its defaults, so an injected empty dict is "
           "falsy and silently replaced by the module-level STATEMENT_CONFIGS "
           "/ CUSTOM_PROCESSORS - backlog",
    strict=True,
)

NON_NUMERIC_USER_ID = pytest.mark.xfail(
    reason="get() calls int() on the user: suffix without guarding, so a "
           "non-numeric id raises a bare ValueError instead of an AppError "
           "with a 404 - backlog",
    strict=True,
)


def make_config(bank_name='AIB', account_type='current', **overrides):
    kwargs = dict(
        bank_name=bank_name,
        account_type=account_type,
        date_config=DateConfig(column='Date', format='%d/%m/%Y'),
        amount_config=AmountConfig(credit_column='In', debit_column='Out'),
        description_column='Description',
    )
    kwargs.update(overrides)
    return StatementConfig(**kwargs)


class FakeRepo:
    """Stands in for StatementFormatRepository, matching its contract:
    get_format_by_id raises RecordNotFound; get_all_formats returns rows."""

    def __init__(self, rows=None):
        self.rows = rows or {}
        self.get_by_id_calls = []

    def get_format_by_id(self, format_id):
        self.get_by_id_calls.append(format_id)
        if format_id not in self.rows:
            raise RecordNotFound('StatementFormat', id=format_id)
        return self.rows[format_id]

    def get_all_formats(self):
        return list(self.rows.values())


def user_row(format_id, config=None, config_json=...):
    """Build a repository row. Pass config_json explicitly to inject a bad one."""
    if config_json is ...:
        config_json = (config or make_config()).to_dict()
    return {'id': format_id, 'config_json': config_json}


class StubCategorizer:
    """Avoids constructing a real TransactionCategorizer, which needs a DB."""

    def categorize(self, descriptions):
        return [
            {'cleaned_description': d, 'party_id': 1, 'confidence': 90}
            for d in descriptions
        ]


class CustomProcessor(StatementProcessor):
    """Stand-in for a bank needing logic a config can't express."""

    def __init__(self, account_id, upload_id, categorizer=None, **kwargs):
        self.extra_kwargs = kwargs
        super().__init__(account_id, upload_id, categorizer)

    @property
    def config(self):
        return make_config(bank_name='Custom')


@pytest.fixture
def builtins():
    return {
        'aib_current': make_config('AIB', 'current'),
        'ptsb_current': make_config('Permanent TSB', 'current'),
    }


@pytest.fixture
def repo():
    return FakeRepo()


@pytest.fixture
def make_registry(builtins, repo):
    def _make(rows=None, custom_processors=None, builtin_configs=None):
        if rows is not None:
            repo.rows = rows
        return StatementFormatRegistry(
            statement_format_repo=repo,
            builtin_configs=builtins if builtin_configs is None else builtin_configs,
            custom_processors=custom_processors,
        )
    return _make


@pytest.fixture
def registry(make_registry):
    return make_registry()


# --------------------------------------------------------------------------- #
# FormatHandle
# --------------------------------------------------------------------------- #
class TestFormatHandle:

    def test_user_formats_are_editable(self):
        handle = FormatHandle(identifier='user:1', source='user', config=make_config())
        assert handle.editable is True

    def test_builtin_formats_are_not_editable(self):
        handle = FormatHandle(
            identifier='builtin:aib_current', source='builtin', config=make_config()
        )
        assert handle.editable is False

    def test_custom_processor_defaults_to_none(self):
        handle = FormatHandle(identifier='user:1', source='user', config=make_config())
        assert handle.custom_processor_cls is None

    def test_is_frozen(self):
        handle = FormatHandle(identifier='user:1', source='user', config=make_config())
        with pytest.raises(Exception):
            handle.identifier = 'user:2'


# --------------------------------------------------------------------------- #
# construction / dependency injection
# --------------------------------------------------------------------------- #
class TestRegistryConstruction:

    def test_injected_dependencies_are_used(self, builtins, repo):
        registry = StatementFormatRegistry(
            statement_format_repo=repo,
            builtin_configs=builtins,
            custom_processors={'aib_current': CustomProcessor},
        )
        assert registry.get('builtin:aib_current').custom_processor_cls is CustomProcessor

    def test_defaults_to_the_real_builtins(self, repo):
        registry = StatementFormatRegistry(statement_format_repo=repo)
        assert registry.get('builtin:ptsb_current').config.bank_name == 'Permanent TSB'

    def test_custom_processors_default_to_none_for_known_keys(self, registry):
        assert registry.get('builtin:aib_current').custom_processor_cls is None

    @EMPTY_INJECTION_IGNORED
    def test_empty_builtins_injection_is_respected(self, repo):
        """Injecting {} should mean 'no built-ins', not 'use the real ones'."""
        registry = StatementFormatRegistry(
            statement_format_repo=repo, builtin_configs={}
        )
        assert registry.builtin_display_names() == set()


# --------------------------------------------------------------------------- #
# get() - built-ins
# --------------------------------------------------------------------------- #
class TestGetBuiltin:

    def test_tagged_identifier(self, registry):
        handle = registry.get('builtin:aib_current')
        assert handle.identifier == 'builtin:aib_current'
        assert handle.source == 'builtin'
        assert handle.config.bank_name == 'AIB'
        assert handle.editable is False

    def test_identifier_round_trips(self, registry):
        first = registry.get('builtin:aib_current')
        assert registry.get(first.identifier) == first

    def test_bare_key_still_resolves(self, registry):
        """Back-compat: accounts.statement_format may hold untagged keys."""
        handle = registry.get('aib_current')
        assert handle.source == 'builtin'
        assert handle.identifier == 'builtin:aib_current'

    def test_custom_processor_attached_when_registered(self, make_registry):
        registry = make_registry(custom_processors={'aib_current': CustomProcessor})
        assert registry.get('builtin:aib_current').custom_processor_cls is CustomProcessor
        assert registry.get('builtin:ptsb_current').custom_processor_cls is None

    def test_unknown_tagged_key_raises_not_found(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('builtin:nope')
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.status_code == 404
        assert exc.value.entity == 'StatementFormat'

    def test_unknown_builtin_lists_what_is_available(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('builtin:nope')
        message = str(exc.value.message)
        assert 'aib_current' in message and 'ptsb_current' in message

    def test_unknown_bare_key_raises_not_found(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('nope')
        assert exc.value.code == ErrorCode.NOT_FOUND

    def test_empty_builtin_key_raises_not_found(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('builtin:')
        assert exc.value.code == ErrorCode.NOT_FOUND

    def test_builtin_lookup_never_touches_the_repository(self, registry, repo):
        registry.get('builtin:aib_current')
        assert repo.get_by_id_calls == []

    def test_lookup_is_case_sensitive(self, registry):
        with pytest.raises(AppError):
            registry.get('builtin:AIB_CURRENT')


# --------------------------------------------------------------------------- #
# get() - user configs
# --------------------------------------------------------------------------- #
class TestGetUser:

    def test_resolves_stored_config(self, make_registry):
        config = make_config('Revolut', 'current')
        registry = make_registry(rows={42: user_row(42, config)})

        handle = registry.get('user:42')
        assert handle.identifier == 'user:42'
        assert handle.source == 'user'
        assert handle.editable is True
        assert handle.config == config

    def test_never_has_a_custom_processor(self, make_registry):
        registry = make_registry(
            rows={42: user_row(42)},
            custom_processors={'42': CustomProcessor, 'user:42': CustomProcessor},
        )
        assert registry.get('user:42').custom_processor_cls is None

    def test_id_is_passed_to_the_repository_as_an_int(self, make_registry, repo):
        registry = make_registry(rows={42: user_row(42)})
        registry.get('user:42')
        assert repo.get_by_id_calls == [42]

    def test_missing_row_raises_not_found(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('user:99')
        assert exc.value.code == ErrorCode.NOT_FOUND
        assert exc.value.status_code == 404

    def test_null_config_json_raises_invalid_format(self, make_registry):
        registry = make_registry(rows={42: user_row(42, config_json=None)})
        with pytest.raises(AppError) as exc:
            registry.get('user:42')
        assert exc.value.code == ErrorCode.INVALID_FORMAT
        assert exc.value.status_code == 500

    def test_config_failing_validation_raises_invalid_format(self, make_registry):
        broken = make_config().to_dict()
        broken['amount_config'] = {}  # neither split columns nor amount column
        registry = make_registry(rows={42: user_row(42, config_json=broken)})

        with pytest.raises(AppError) as exc:
            registry.get('user:42')
        assert exc.value.code == ErrorCode.INVALID_FORMAT
        assert exc.value.status_code == 500

    def test_config_missing_required_keys_raises_invalid_format(self, make_registry):
        incomplete = {'bank_name': 'AIB'}  # no account_type, no description_column
        registry = make_registry(rows={42: user_row(42, config_json=incomplete)})

        with pytest.raises(AppError) as exc:
            registry.get('user:42')
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    def test_stored_config_errors_are_500_not_404(self, make_registry):
        """A broken stored config is our bug, not a bad request from the user."""
        registry = make_registry(rows={42: user_row(42, config_json=None)})
        with pytest.raises(AppError) as exc:
            registry.get('user:42')
        assert exc.value.status_code == 500

    @NON_NUMERIC_USER_ID
    def test_non_numeric_user_id_raises_app_error(self, registry):
        with pytest.raises(AppError) as exc:
            registry.get('user:abc')
        assert exc.value.status_code in (400, 404)

    @NON_NUMERIC_USER_ID
    def test_empty_user_id_raises_app_error(self, registry):
        with pytest.raises(AppError):
            registry.get('user:')


# --------------------------------------------------------------------------- #
# list_all
# --------------------------------------------------------------------------- #
class TestListAll:

    def test_builtins_listed_first_in_declaration_order(self, registry):
        listed = registry.list_all()
        assert [e['identifier'] for e in listed] == [
            'builtin:aib_current', 'builtin:ptsb_current'
        ]

    def test_builtin_entry_shape(self, registry):
        entry = registry.list_all()[0]
        assert entry == {
            'identifier': 'builtin:aib_current',
            'source': 'builtin',
            'editable': False,
            'bank_name': 'AIB',
            'account_type': 'current',
            'display_name': 'AIB current',
            'has_custom_processor': False,
        }

    def test_has_custom_processor_flag(self, make_registry):
        registry = make_registry(custom_processors={'aib_current': CustomProcessor})
        flags = {e['identifier']: e['has_custom_processor']
                 for e in registry.list_all()}
        assert flags['builtin:aib_current'] is True
        assert flags['builtin:ptsb_current'] is False

    def test_user_entries_follow_builtins(self, make_registry):
        registry = make_registry(
            rows={7: user_row(7, make_config('Revolut', 'current'))}
        )
        listed = registry.list_all()
        assert listed[-1] == {
            'identifier': 'user:7',
            'source': 'user',
            'editable': True,
            'bank_name': 'Revolut',
            'account_type': 'current',
            'display_name': 'Revolut current',
            'has_custom_processor': False,
        }

    def test_user_entries_never_claim_a_custom_processor(self, make_registry):
        registry = make_registry(
            rows={7: user_row(7)},
            custom_processors={'7': CustomProcessor},
        )
        assert registry.list_all()[-1]['has_custom_processor'] is False

    def test_empty_registry(self, make_registry):
        registry = make_registry(builtin_configs={'x': make_config()})
        assert len(registry.list_all()) == 1

    def test_null_config_row_is_skipped(self, make_registry):
        registry = make_registry(rows={7: user_row(7, config_json=None)})
        assert all(e['source'] == 'builtin' for e in registry.list_all())

    def test_invalid_config_row_is_skipped(self, make_registry):
        broken = make_config().to_dict()
        broken['amount_config'] = {}
        registry = make_registry(rows={7: user_row(7, config_json=broken)})
        assert all(e['source'] == 'builtin' for e in registry.list_all())

    def test_one_bad_row_does_not_hide_the_good_ones(self, make_registry):
        registry = make_registry(rows={
            7: user_row(7, config_json=None),
            8: user_row(8, make_config('Revolut', 'current')),
        })
        identifiers = [e['identifier'] for e in registry.list_all()]
        assert 'user:8' in identifiers
        assert 'user:7' not in identifiers

    def test_listed_identifiers_are_resolvable(self, make_registry):
        registry = make_registry(rows={7: user_row(7)})
        for entry in registry.list_all():
            assert registry.get(entry['identifier']).identifier == entry['identifier']


# --------------------------------------------------------------------------- #
# builtin_display_names
# --------------------------------------------------------------------------- #
class TestBuiltinDisplayNames:

    def test_returns_display_names(self, registry):
        assert registry.builtin_display_names() == {
            'AIB current', 'Permanent TSB current'
        }

    def test_excludes_user_formats(self, make_registry):
        registry = make_registry(rows={7: user_row(7, make_config('Revolut', 'x'))})
        assert 'Revolut x' not in registry.builtin_display_names()

    def test_real_builtins_are_distinct(self):
        """The collision check is only meaningful if built-ins don't collide."""
        from src.statements.configs import STATEMENT_CONFIGS

        names = [cfg.display_name for cfg in STATEMENT_CONFIGS.values()]
        assert len(names) == len(set(names))


# --------------------------------------------------------------------------- #
# get_processor
# --------------------------------------------------------------------------- #
class TestGetProcessor:

    def test_builds_configurable_processor_by_default(self, registry):
        processor = get_processor(
            'builtin:aib_current', account_id=1, upload_id=2, registry=registry,
            categorizer=StubCategorizer(),
        )
        assert isinstance(processor, ConfigurableStatementProcessor)
        assert processor.config.bank_name == 'AIB'
        assert processor.account_id == 1
        assert processor.upload_id == 2

    def test_builds_processor_for_user_config(self, make_registry):
        registry = make_registry(rows={42: user_row(42, make_config('Revolut', 'x'))})
        processor = get_processor('user:42', account_id=1, upload_id=2,
                                  registry=registry, categorizer=StubCategorizer())
        assert processor.config.display_name == 'Revolut x'

    def test_dispatches_to_custom_processor(self, make_registry):
        registry = make_registry(custom_processors={'aib_current': CustomProcessor})
        processor = get_processor('builtin:aib_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=StubCategorizer())
        assert isinstance(processor, CustomProcessor)
        assert processor.account_id == 1

    def test_kwargs_forwarded_to_custom_processor_only(self, make_registry):
        registry = make_registry(custom_processors={'aib_current': CustomProcessor})
        processor = get_processor('builtin:aib_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=StubCategorizer(),
                                  extra='value')
        assert processor.extra_kwargs == {'extra': 'value'}

    def test_kwargs_ignored_for_configurable_processor(self, registry):
        processor = get_processor('builtin:ptsb_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=StubCategorizer(),
                                  extra='value')
        assert isinstance(processor, ConfigurableStatementProcessor)

    def test_categorizer_is_injected(self, registry):
        sentinel = object()
        processor = get_processor('builtin:aib_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=sentinel)
        assert processor.categorizer is sentinel

    def test_custom_processor_receives_the_categorizer(self, make_registry):
        sentinel = object()
        registry = make_registry(custom_processors={'aib_current': CustomProcessor})
        processor = get_processor('builtin:aib_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=sentinel)
        assert processor.categorizer is sentinel

    def test_lookup_errors_propagate(self, registry):
        with pytest.raises(AppError) as exc:
            get_processor('builtin:nope', account_id=1, upload_id=2, registry=registry)
        assert exc.value.code == ErrorCode.NOT_FOUND

    def test_bare_key_accepted(self, registry):
        processor = get_processor('aib_current', account_id=1, upload_id=2,
                                  registry=registry, categorizer=StubCategorizer())
        assert processor.config.bank_name == 'AIB'

    def test_returned_processor_can_run(self, registry):
        processor = get_processor(
            'builtin:aib_current', account_id=1, upload_id=2,
            registry=registry, categorizer=StubCategorizer(),
        )
        result = processor.process_statement(
            [{'Date': '15/01/2024', 'Description': 'TESCO', 'In': '', 'Out': '10.00'}]
        )
        assert result['amount'].tolist() == [-10.00]


# --------------------------------------------------------------------------- #
# against the real repository
# --------------------------------------------------------------------------- #
class TestAgainstRealRepository:
    """The fakes above encode an assumed repository contract. These prove the
    real StatementFormatRepository behaves the same way."""

    @pytest.fixture
    def real_registry(self, app_with_db):
        from src.database.repositories.statement_format import (
            StatementFormatRepository,
        )

        with app_with_db.app_context():
            yield StatementFormatRegistry(
                statement_format_repo=StatementFormatRepository()
            )

    @pytest.fixture
    def stored(self, real_registry):
        repo = real_registry._repo
        return repo.add_format('Revolut', 'current', make_config('Revolut',
                                                                 'current').to_dict())

    def test_round_trips_a_stored_config(self, real_registry, stored):
        handle = real_registry.get(f"user:{stored['id']}")
        assert handle.source == 'user'
        assert handle.config == make_config('Revolut', 'current')

    def test_missing_row_raises_not_found(self, real_registry):
        with pytest.raises(AppError) as exc:
            real_registry.get('user:999')
        assert exc.value.code == ErrorCode.NOT_FOUND

    def test_corrupt_row_raises_invalid_format(self, real_registry, stored, db_manager):
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE statement_formats SET config_json = ? WHERE id = ?",
                ('not json{', stored['id']),
            )
        with pytest.raises(AppError) as exc:
            real_registry.get(f"user:{stored['id']}")
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    def test_list_all_includes_builtins_and_stored(self, real_registry, stored):
        identifiers = [e['identifier'] for e in real_registry.list_all()]
        assert 'builtin:aib_current' in identifiers
        assert f"user:{stored['id']}" in identifiers

    def test_list_all_skips_a_corrupt_row(self, real_registry, stored, db_manager):
        with db_manager.transaction() as conn:
            conn.execute(
                "UPDATE statement_formats SET config_json = ? WHERE id = ?",
                ('not json{', stored['id']),
            )
        identifiers = [e['identifier'] for e in real_registry.list_all()]
        assert f"user:{stored['id']}" not in identifiers
        assert 'builtin:aib_current' in identifiers

    def test_get_processor_end_to_end(self, real_registry, stored):
        processor = get_processor(f"user:{stored['id']}", account_id=1, upload_id=2,
                                  registry=real_registry,
                                  categorizer=StubCategorizer())
        assert isinstance(processor, ConfigurableStatementProcessor)
        assert processor.config.bank_name == 'Revolut'