"""
Tests for src/statements/base.py.

Covers the declarative config dataclasses (`AmountConfig`, `DateConfig`,
`StatementConfig`), the `ProcessingWarning` value object, and the
`StatementProcessor` pipeline via `ConfigurableStatementProcessor`.

The categorizer is injected as a stub throughout: it owns fuzzy matching and
writes new parties to the database, neither of which belongs in a test of the
parsing pipeline. Its own behaviour is covered in tests/test_categorizer/.
"""
import pandas as pd
import pytest

from src.api.utils.errors import AppError, ErrorCode
BLANK_AMOUNT_COLUMN_ACCEPTED = pytest.mark.xfail(
    reason="StatementConfig.__post_init__ checks `amount_column is not None` "
           "while the split-column check uses truthiness, so amount_column='' "
           "passes validation and fails much later with a pandas KeyError "
           "- backlog",
    strict=True,
)

CREDIT_INDICATOR_CASE_SENSITIVE = pytest.mark.xfail(
    reason="_parse_single_amount compares the indicator column with `==`, so "
           "a 'cr' row in a config expecting 'CR' is silently treated as a "
           "debit and has its sign flipped - backlog",
    strict=True,
)

EMPTY_AFTER_FILTERING = pytest.mark.xfail(
    reason="a statement whose rows are all filtered or dropped reaches "
           "_categorize with an empty frame and raises ValueError('Columns "
           "must be same length as key') instead of returning an empty "
           "result - backlog",
    strict=True,
)

from src.statements.base import (
    AmountConfig,
    ConfigurableStatementProcessor,
    DateConfig,
    ProcessingWarning,
    StatementConfig,
    StatementProcessor,
)


class StubCategorizer:
    """Records what it was asked to categorize and returns predictable output."""

    def __init__(self, party_id=7, confidence=95):
        self.seen = None
        self._party_id = party_id
        self._confidence = confidence

    def categorize(self, descriptions):
        self.seen = list(descriptions)
        return [
            {
                'cleaned_description': d.upper(),
                'party_id': self._party_id,
                'confidence': self._confidence,
            }
            for d in descriptions
        ]


@pytest.fixture
def categorizer():
    return StubCategorizer()


def split_config(**overrides):
    """Config with separate Credit/Debit columns (the AIB shape)."""
    kwargs = dict(
        bank_name='AIB',
        account_type='current',
        date_config=DateConfig(column='Date', format='%d/%m/%Y'),
        amount_config=AmountConfig(credit_column='In', debit_column='Out'),
        description_column='Description',
    )
    kwargs.update(overrides)
    return StatementConfig(**kwargs)


def signed_config(**overrides):
    """Config with one signed amount column (the Revolut shape)."""
    kwargs = dict(
        bank_name='Revolut',
        account_type='current',
        date_config=DateConfig(column='Date', format='%Y-%m-%d'),
        amount_config=AmountConfig(amount_column='Amount', signed_amount=True),
        description_column='Description',
    )
    kwargs.update(overrides)
    return StatementConfig(**kwargs)


def indicator_config(**overrides):
    """Config with an unsigned amount plus a CR/DR indicator column."""
    kwargs = dict(
        bank_name='PTSB',
        account_type='current',
        date_config=DateConfig(column='Date', format='%d/%m/%Y'),
        amount_config=AmountConfig(
            amount_column='Amount',
            credit_indicator_column='Type',
            credit_indicator_value='CR',
        ),
        description_column='Description',
    )
    kwargs.update(overrides)
    return StatementConfig(**kwargs)


@pytest.fixture
def make_processor(categorizer):
    """Factory: make_processor(config, account_id=1, upload_id=2) -> processor."""
    def _make(config, account_id=1, upload_id=2, categorizer_override=None):
        return ConfigurableStatementProcessor(
            statement_config=config,
            account_id=account_id,
            upload_id=upload_id,
            categorizer=categorizer_override or categorizer,
        )
    return _make


@pytest.fixture
def split_rows():
    return [
        {'Date': '15/01/2024', 'Description': 'TESCO', 'In': '', 'Out': '25.99'},
        {'Date': '16/01/2024', 'Description': 'SALARY', 'In': '2000.00', 'Out': ''},
    ]


# --------------------------------------------------------------------------- #
# AmountConfig / DateConfig defaults
# --------------------------------------------------------------------------- #
class TestConfigDefaults:

    def test_amount_config_defaults(self):
        cfg = AmountConfig(amount_column='Amount')
        assert cfg.currency_symbols == ['€', '$', '£']
        assert cfg.decimal_separator == '.'
        assert cfg.thousands_separator == ','
        assert cfg.debit_is_negative is True
        assert cfg.signed_amount is False

    def test_currency_symbols_not_shared_between_instances(self):
        a, b = AmountConfig(amount_column='X'), AmountConfig(amount_column='Y')
        a.currency_symbols.append('¥')
        assert b.currency_symbols == ['€', '$', '£']

    def test_date_config_defaults_to_dayfirst(self):
        cfg = DateConfig(column='Date')
        assert cfg.format is None
        assert cfg.dayfirst is True


# --------------------------------------------------------------------------- #
# StatementConfig validation
# --------------------------------------------------------------------------- #
class TestStatementConfigValidation:

    def test_split_columns_accepted(self):
        assert split_config().amount_config.credit_column == 'In'

    def test_single_amount_column_accepted(self):
        assert signed_config().amount_config.amount_column == 'Amount'

    def test_no_amount_configuration_rejected(self):
        with pytest.raises(ValueError) as exc:
            split_config(amount_config=AmountConfig())
        assert 'credit_column/debit_column' in str(exc.value)

    def test_credit_column_without_debit_column_rejected(self):
        with pytest.raises(ValueError):
            split_config(amount_config=AmountConfig(credit_column='In'))

    def test_debit_column_without_credit_column_rejected(self):
        with pytest.raises(ValueError):
            split_config(amount_config=AmountConfig(debit_column='Out'))

    @BLANK_AMOUNT_COLUMN_ACCEPTED
    def test_empty_string_amount_column_rejected(self):
        """'' names no column, so it should fail validation like None does."""
        with pytest.raises(ValueError) as exc:
            split_config(amount_config=AmountConfig(amount_column=''))
        assert 'credit_column/debit_column' in str(exc.value)

    @BLANK_AMOUNT_COLUMN_ACCEPTED
    def test_blank_amount_column_fails_late_and_unhelpfully(self, make_processor):
        """Today nothing catches it: required_columns omits the blank name, so
        validation passes and the import dies on a bare `KeyError: ''`.
        Whatever the fix, the user should get a real error, not a KeyError."""
        config = split_config(amount_config=AmountConfig(amount_column=''))
        rows = [{'Date': '15/01/2024', 'Description': 'X', 'Amount': '1.00'}]
        with pytest.raises(AppError):
            make_processor(config).process_statement(rows)


class TestDefaultsValidation:

    @pytest.mark.parametrize('defaults', [
        {'is_kids': True},
        {'is_one_off': False},
        {'is_kids': True, 'is_one_off': True},
        {},
    ])
    def test_allowed_defaults_accepted(self, defaults):
        assert split_config(defaults=defaults).defaults == defaults

    def test_unknown_key_rejected(self):
        with pytest.raises(ValueError) as exc:
            split_config(defaults={'amount': 10})
        assert "'amount' is not a permitted default field" in str(exc.value)
        assert 'must come from' in str(exc.value)

    def test_wrong_type_rejected(self):
        with pytest.raises(ValueError) as exc:
            split_config(defaults={'is_kids': 'yes'})
        assert "Default for 'is_kids' must be bool" in str(exc.value)

    def test_key_and_value_errors_reported_together(self):
        with pytest.raises(ValueError) as exc:
            split_config(defaults={'party_id': 1, 'is_one_off': 'no'})
        message = str(exc.value)
        assert "'party_id' is not a permitted default field" in message
        assert "Default for 'is_one_off' must be bool" in message

    def test_every_bad_key_is_listed(self):
        with pytest.raises(ValueError) as exc:
            split_config(defaults={'amount': 1, 'description': 'x'})
        assert "'amount'" in str(exc.value)
        assert "'description'" in str(exc.value)

    def test_int_accepted_for_bool_field(self):
        """bool is a subclass of int, but not vice versa - 1 is rejected."""
        with pytest.raises(ValueError):
            split_config(defaults={'is_kids': 1})


# --------------------------------------------------------------------------- #
# StatementConfig properties
# --------------------------------------------------------------------------- #
class TestRequiredColumns:

    def test_split_columns(self):
        assert split_config().required_columns == ['Date', 'Description', 'In', 'Out']

    def test_single_amount_column(self):
        assert signed_config().required_columns == ['Date', 'Description', 'Amount']

    def test_indicator_column_included(self):
        assert indicator_config().required_columns == [
            'Date', 'Description', 'Amount', 'Type'
        ]

    def test_optional_columns_not_required(self):
        cfg = split_config(balance_column='Balance', reference_column='Ref')
        assert 'Balance' not in cfg.required_columns
        assert 'Ref' not in cfg.required_columns

    def test_duplicates_collapsed_preserving_order(self):
        cfg = signed_config(
            date_config=DateConfig(column='Detail'),
            description_column='Detail',
        )
        assert cfg.required_columns == ['Detail', 'Amount']


class TestDisplayName:

    def test_combines_bank_and_account_type(self):
        assert split_config().display_name == 'AIB current'


# --------------------------------------------------------------------------- #
# serialization
# --------------------------------------------------------------------------- #
class TestSerialization:

    def test_to_dict_is_json_safe_and_nested(self):
        data = split_config().to_dict()
        assert data['bank_name'] == 'AIB'
        assert data['date_config'] == {
            'column': 'Date', 'format': '%d/%m/%Y', 'dayfirst': True
        }
        assert data['amount_config']['credit_column'] == 'In'

    def test_round_trip(self):
        cfg = split_config(
            exclude_patterns=['^OPENING'], defaults={'is_kids': True},
            balance_column='Balance',
        )
        assert StatementConfig.from_dict(cfg.to_dict()) == cfg

    def test_from_dict_fills_missing_optional_keys(self):
        cfg = StatementConfig.from_dict({
            'bank_name': 'AIB',
            'account_type': 'current',
            'description_column': 'Description',
            'date_config': {'column': 'Date'},
            'amount_config': {'amount_column': 'Amount'},
        })
        assert cfg.skip_rows_start == 0
        assert cfg.exclude_patterns == []
        assert cfg.date_config.dayfirst is True

    def test_from_dict_drops_unknown_keys(self):
        cfg = StatementConfig.from_dict({
            'bank_name': 'AIB',
            'account_type': 'current',
            'description_column': 'Description',
            'legacy_field': 'ignored',
            'date_config': {'column': 'Date', 'legacy': 1},
            'amount_config': {'amount_column': 'Amount', 'legacy': 2},
        })
        assert not hasattr(cfg, 'legacy_field')

    def test_from_dict_missing_required_key_raises(self):
        with pytest.raises(TypeError):
            StatementConfig.from_dict({
                'bank_name': 'AIB',
                'date_config': {'column': 'Date'},
                'amount_config': {'amount_column': 'Amount'},
            })

    def test_from_dict_null_sub_configs_fall_back_to_defaults(self):
        with pytest.raises(TypeError):
            # DateConfig.column is required, so an explicit null date_config
            # cannot produce a valid config.
            StatementConfig.from_dict({
                'bank_name': 'AIB',
                'account_type': 'current',
                'description_column': 'Description',
                'date_config': None,
                'amount_config': {'amount_column': 'Amount'},
            })

    def test_from_dict_does_not_mutate_input(self):
        data = split_config().to_dict()
        StatementConfig.from_dict(data)
        assert 'date_config' in data and 'amount_config' in data

    def test_from_dict_revalidates(self):
        data = signed_config().to_dict()
        data['amount_config'] = {}
        with pytest.raises(ValueError):
            StatementConfig.from_dict(data)

    def test_builtin_configs_round_trip(self):
        from src.statements.configs import STATEMENT_CONFIGS

        for cfg in STATEMENT_CONFIGS.values():
            assert StatementConfig.from_dict(cfg.to_dict()) == cfg


# --------------------------------------------------------------------------- #
# ProcessingWarning
# --------------------------------------------------------------------------- #
class TestProcessingWarning:

    def test_to_dict(self):
        warning = ProcessingWarning(code='X', message='m', details={'a': 1})
        assert warning.to_dict() == {'code': 'X', 'message': 'm', 'details': {'a': 1}}

    def test_details_default_empty_and_not_shared(self):
        a = ProcessingWarning(code='X', message='m')
        b = ProcessingWarning(code='Y', message='m')
        a.details['k'] = 1
        assert b.details == {}


# --------------------------------------------------------------------------- #
# processor construction
# --------------------------------------------------------------------------- #
class TestProcessorConstruction:

    def test_stores_ids_and_starts_empty(self, make_processor, categorizer):
        processor = make_processor(split_config(), account_id=3, upload_id=4)
        assert processor.account_id == 3
        assert processor.upload_id == 4
        assert processor.categorizer is categorizer
        assert processor.transactions is None
        assert processor.warnings == []

    def test_configurable_processor_exposes_its_config(self, make_processor):
        config = split_config()
        assert make_processor(config).config is config

    def test_abstract_base_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            StatementProcessor(account_id=1, upload_id=2)

    def test_subclass_must_implement_config(self):
        class Incomplete(StatementProcessor):
            pass

        with pytest.raises(TypeError):
            Incomplete(account_id=1, upload_id=2)


# --------------------------------------------------------------------------- #
# process_statement - happy path and output shape
# --------------------------------------------------------------------------- #
class TestProcessStatement:

    def test_output_has_exactly_the_expected_columns(
        self, make_processor, split_rows
    ):
        result = make_processor(split_config()).process_statement(split_rows)
        assert list(result.columns) == StatementProcessor.OUTPUT_COLUMNS

    def test_returns_one_row_per_transaction(self, make_processor, split_rows):
        assert len(make_processor(split_config()).process_statement(split_rows)) == 2

    def test_result_also_stored_on_the_processor(self, make_processor, split_rows):
        processor = make_processor(split_config())
        result = processor.process_statement(split_rows)
        pd.testing.assert_frame_equal(processor.transactions, result)

    def test_index_is_reset(self, make_processor, split_rows):
        config = split_config(exclude_patterns=['TESCO'])
        result = make_processor(config).process_statement(split_rows)
        assert list(result.index) == [0]

    def test_ids_stamped_on_every_row(self, make_processor, split_rows):
        result = make_processor(
            split_config(), account_id=11, upload_id=22
        ).process_statement(split_rows)
        assert (result['account_id'] == 11).all()
        assert (result['upload_id'] == 22).all()

    def test_ids_are_coerced_to_int(self, make_processor, split_rows):
        result = make_processor(
            split_config(), account_id='11', upload_id='22'
        ).process_statement(split_rows)
        assert result['account_id'].tolist() == [11, 11]

    def test_categorizer_receives_cleaned_descriptions(
        self, make_processor, split_rows, categorizer
    ):
        make_processor(split_config()).process_statement(split_rows)
        assert categorizer.seen == ['TESCO', 'SALARY']

    def test_categorizer_output_mapped_onto_columns(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert result['cleaned_description'].tolist() == ['TESCO', 'SALARY']
        assert result['party_id'].tolist() == [7, 7]
        assert result['confidence'].tolist() == [95, 95]

    def test_missing_output_columns_are_filled_with_none(
        self, make_processor, split_rows
    ):
        result = make_processor(split_config()).process_statement(split_rows)
        assert result['receipt_id'].isna().all()

    def test_source_only_columns_are_dropped(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'TESCO', 'In': '',
                 'Out': '1.00', 'Balance': '99.00'}]
        result = make_processor(split_config(balance_column='Balance')
                                ).process_statement(rows)
        assert 'Balance' not in result.columns


# --------------------------------------------------------------------------- #
# skip rows
# --------------------------------------------------------------------------- #
class TestSkipRows:

    @pytest.fixture
    def padded_rows(self, split_rows):
        junk = {'Date': 'Statement', 'Description': 'Header', 'In': '', 'Out': ''}
        return [junk, *split_rows, junk]

    def test_skip_start(self, make_processor, padded_rows):
        config = split_config(skip_rows_start=1, skip_rows_end=1)
        result = make_processor(config).process_statement(padded_rows)
        assert result['description'].tolist() == ['TESCO', 'SALARY']

    def test_skip_start_only(self, make_processor, split_rows):
        config = split_config(skip_rows_start=1)
        result = make_processor(config).process_statement(split_rows)
        assert result['description'].tolist() == ['SALARY']

    def test_skip_end_only(self, make_processor, split_rows):
        config = split_config(skip_rows_end=1)
        result = make_processor(config).process_statement(split_rows)
        assert result['description'].tolist() == ['TESCO']

    def test_zero_skip_keeps_everything(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert len(result) == 2


# --------------------------------------------------------------------------- #
# column validation
# --------------------------------------------------------------------------- #
class TestRequiredColumnValidation:

    def test_missing_column_raises_app_error(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'TESCO', 'In': ''}]
        with pytest.raises(AppError) as exc:
            make_processor(split_config()).process_statement(rows)
        assert exc.value.code == ErrorCode.INVALID_FORMAT
        assert exc.value.status_code == 422

    def test_error_details_are_structured_for_the_ui(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'TESCO', 'In': ''}]
        with pytest.raises(AppError) as exc:
            make_processor(split_config(), account_id=9).process_statement(rows)

        details = exc.value.details
        assert details['missing_columns'] == ['Out']
        assert details['found_columns'] == ['Date', 'Description', 'In']
        assert details['required_columns'] == ['Date', 'Description', 'In', 'Out']
        assert details['statement_format'] == 'AIB current'
        assert details['account_id'] == 9

    def test_message_names_the_format_and_the_gap(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'TESCO', 'In': ''}]
        with pytest.raises(AppError) as exc:
            make_processor(split_config()).process_statement(rows)
        message = str(exc.value.message)
        assert "'AIB current'" in message
        assert 'Out' in message

    def test_every_missing_column_listed(self, make_processor):
        rows = [{'Date': '15/01/2024'}]
        with pytest.raises(AppError) as exc:
            make_processor(split_config()).process_statement(rows)
        assert exc.value.details['missing_columns'] == ['Description', 'In', 'Out']

    def test_empty_input_reports_no_columns(self, make_processor):
        with pytest.raises(AppError) as exc:
            make_processor(split_config()).process_statement([])
        assert exc.value.details['found_columns'] == []
        assert '(no columns)' in str(exc.value.message)

    def test_extra_columns_are_tolerated(self, make_processor, split_rows):
        rows = [{**r, 'Unexpected': 'x'} for r in split_rows]
        assert len(make_processor(split_config()).process_statement(rows)) == 2

    def test_validation_runs_after_skip_rows(self, make_processor, split_rows):
        """Skipping rows never changes the column set, so a valid file stays valid."""
        config = split_config(skip_rows_start=1)
        assert len(make_processor(config).process_statement(split_rows)) == 1


# --------------------------------------------------------------------------- #
# row filtering
# --------------------------------------------------------------------------- #
class TestFilterRows:

    def test_matching_rows_are_dropped(self, make_processor, split_rows):
        config = split_config(exclude_patterns=['OPENING BALANCE'])
        rows = [{'Date': '14/01/2024', 'Description': 'OPENING BALANCE',
                 'In': '', 'Out': ''}, *split_rows]
        result = make_processor(config).process_statement(rows)
        assert 'OPENING BALANCE' not in result['description'].tolist()

    def test_match_is_case_insensitive(self, make_processor, split_rows):
        config = split_config(exclude_patterns=['tesco'])
        result = make_processor(config).process_statement(split_rows)
        assert result['description'].tolist() == ['SALARY']

    def test_patterns_are_regexes(self, make_processor, split_rows):
        config = split_config(exclude_patterns=[r'^TES\w+$'])
        result = make_processor(config).process_statement(split_rows)
        assert result['description'].tolist() == ['SALARY']

    def test_substring_match_not_anchored(self, make_processor, split_rows):
        config = split_config(exclude_patterns=['ESC'])
        result = make_processor(config).process_statement(split_rows)
        assert result['description'].tolist() == ['SALARY']

    @EMPTY_AFTER_FILTERING
    def test_multiple_patterns_all_applied(self, make_processor, split_rows):
        config = split_config(exclude_patterns=['TESCO', 'SALARY'])
        assert make_processor(config).process_statement(split_rows).empty

    def test_no_patterns_keeps_everything(self, make_processor, split_rows):
        assert len(make_processor(split_config()).process_statement(split_rows)) == 2

    def test_null_descriptions_are_not_dropped_by_filters(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': None, 'In': '', 'Out': '1.00'}]
        config = split_config(exclude_patterns=['TESCO'])
        assert len(make_processor(config).process_statement(rows)) == 1


# --------------------------------------------------------------------------- #
# date parsing
# --------------------------------------------------------------------------- #
class TestDateParsing:

    def test_configured_format_used(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert result['transaction_date'].tolist() == [
            pd.Timestamp('2024-01-15'), pd.Timestamp('2024-01-16')
        ]

    def test_dayfirst_inference_without_a_format(self, make_processor):
        config = split_config(date_config=DateConfig(column='Date', dayfirst=True))
        rows = [{'Date': '03/04/2024', 'Description': 'X', 'In': '', 'Out': '1.00'}]
        result = make_processor(config).process_statement(rows)
        assert result['transaction_date'][0] == pd.Timestamp('2024-04-03')

    def test_iso_dates_parse_even_when_dayfirst_is_set(self, make_processor):
        config = split_config(date_config=DateConfig(column='Date', dayfirst=True))
        rows = [{'Date': '2024-01-15', 'Description': 'X', 'In': '', 'Out': '1.00'}]
        result = make_processor(config).process_statement(rows)
        assert result['transaction_date'][0] == pd.Timestamp('2024-01-15')

    def test_falls_back_when_configured_format_is_wrong(self, make_processor):
        """A file that doesn't match the config still imports via the fallbacks."""
        config = split_config(date_config=DateConfig(column='Date', format='%d/%m/%Y'))
        rows = [{'Date': '2022-10-13T01:02:03Z', 'Description': 'X',
                 'In': '', 'Out': '1.00'}]
        result = make_processor(config).process_statement(rows)
        # Parsed via the ISO8601 candidate, which keeps the UTC offset.
        assert result['transaction_date'][0] == pd.Timestamp(
            '2022-10-13 01:02:03', tz='UTC'
        )

    def test_best_format_wins_over_a_partial_match(self, make_processor):
        """13/01 is only valid dayfirst, so the dayfirst candidate must win."""
        config = split_config(date_config=DateConfig(column='Date', format=None))
        rows = [
            {'Date': '13/01/2024', 'Description': 'A', 'In': '', 'Out': '1.00'},
            {'Date': '14/01/2024', 'Description': 'B', 'In': '', 'Out': '1.00'},
        ]
        result = make_processor(config).process_statement(rows)
        assert result['transaction_date'].tolist() == [
            pd.Timestamp('2024-01-13'), pd.Timestamp('2024-01-14')
        ]

    def test_unparseable_rows_are_dropped(self, make_processor):
        rows = [
            {'Date': '15/01/2024', 'Description': 'GOOD', 'In': '', 'Out': '1.00'},
            {'Date': 'not a date', 'Description': 'BAD', 'In': '', 'Out': '1.00'},
        ]
        result = make_processor(split_config()).process_statement(rows)
        assert result['description'].tolist() == ['GOOD']

    def test_dropped_rows_raise_a_warning(self, make_processor):
        rows = [
            {'Date': '15/01/2024', 'Description': 'GOOD', 'In': '', 'Out': '1.00'},
            {'Date': 'not a date', 'Description': 'BAD', 'In': '', 'Out': '1.00'},
        ]
        processor = make_processor(split_config())
        processor.process_statement(rows)

        assert len(processor.warnings) == 1
        warning = processor.warnings[0]
        assert warning.code == 'DATES_UNPARSEABLE'
        assert warning.details['dropped'] == 1
        assert warning.details['total'] == 2
        assert warning.details['column'] == 'Date'
        assert warning.details['sample_values'] == ['not a date']

    def test_no_warning_when_everything_parses(self, make_processor, split_rows):
        processor = make_processor(split_config())
        processor.process_statement(split_rows)
        assert processor.warnings == []

    def test_all_dates_unparseable_raises(self, make_processor):
        rows = [{'Date': 'rubbish', 'Description': 'X', 'In': '', 'Out': '1.00'}]
        with pytest.raises(AppError) as exc:
            make_processor(split_config()).process_statement(rows)

        assert exc.value.code == ErrorCode.INVALID_FORMAT
        assert exc.value.status_code == 422
        assert exc.value.details['column'] == 'Date'
        assert exc.value.details['sample_values'] == ['rubbish']
        assert exc.value.details['formats_tried']

    @EMPTY_AFTER_FILTERING
    def test_all_dates_null_is_not_an_error(self, make_processor):
        """An empty date column yields no rows rather than blowing up."""
        rows = [{'Date': None, 'Description': 'X', 'In': '', 'Out': '1.00'}]
        processor = make_processor(split_config())
        assert processor.process_statement(rows).empty
        assert processor.warnings[0].code == 'DATES_UNPARSEABLE'


# --------------------------------------------------------------------------- #
# amount parsing
# --------------------------------------------------------------------------- #
class TestSplitAmounts:

    def test_debits_negative_credits_positive(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert result['amount'].tolist() == [-25.99, 2000.00]
        assert result['is_credit'].tolist() == [False, True]

    def test_debit_is_negative_false_adds_columns(self, make_processor, split_rows):
        config = split_config(amount_config=AmountConfig(
            credit_column='In', debit_column='Out', debit_is_negative=False
        ))
        result = make_processor(config).process_statement(split_rows)
        assert result['amount'].tolist() == [25.99, 2000.00]

    def test_blank_side_treated_as_zero(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'X', 'In': '', 'Out': '10.00'}]
        result = make_processor(split_config()).process_statement(rows)
        assert result['amount'][0] == -10.00

    def test_both_sides_populated_nets_off(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'X',
                 'In': '30.00', 'Out': '10.00'}]
        result = make_processor(split_config()).process_statement(rows)
        assert result['amount'][0] == 20.00
        assert result['is_credit'][0] is True or bool(result['is_credit'][0])


class TestSignedAmounts:

    @pytest.fixture
    def rows(self):
        return [
            {'Date': '2024-01-15', 'Description': 'TESCO', 'Amount': '-25.99'},
            {'Date': '2024-01-16', 'Description': 'SALARY', 'Amount': '2000.00'},
        ]

    def test_sign_determines_direction(self, make_processor, rows):
        result = make_processor(signed_config()).process_statement(rows)
        assert result['amount'].tolist() == [-25.99, 2000.00]
        assert result['is_credit'].tolist() == [False, True]

    def test_zero_is_not_a_credit(self, make_processor):
        rows = [{'Date': '2024-01-15', 'Description': 'X', 'Amount': '0.00'}]
        result = make_processor(signed_config()).process_statement(rows)
        assert bool(result['is_credit'][0]) is False


class TestIndicatorAmounts:

    @pytest.fixture
    def rows(self):
        return [
            {'Date': '15/01/2024', 'Description': 'TESCO',
             'Amount': '25.99', 'Type': 'DR'},
            {'Date': '16/01/2024', 'Description': 'SALARY',
             'Amount': '2000.00', 'Type': 'CR'},
        ]

    def test_indicator_sets_sign_and_flag(self, make_processor, rows):
        result = make_processor(indicator_config()).process_statement(rows)
        assert result['amount'].tolist() == [-25.99, 2000.00]
        assert result['is_credit'].tolist() == [False, True]

    def test_unrecognised_indicator_treated_as_debit(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'X',
                 'Amount': '5.00', 'Type': 'other'}]
        result = make_processor(indicator_config()).process_statement(rows)
        assert result['amount'][0] == -5.00

    @CREDIT_INDICATOR_CASE_SENSITIVE
    def test_indicator_match_should_be_case_insensitive(self, make_processor):
        """A 'cr' row is a credit. Today it is silently signed as a debit."""
        rows = [{'Date': '15/01/2024', 'Description': 'X',
                 'Amount': '5.00', 'Type': 'cr'}]
        result = make_processor(indicator_config()).process_statement(rows)
        assert result['amount'][0] == 5.00
        assert bool(result['is_credit'][0]) is True

    @CREDIT_INDICATOR_CASE_SENSITIVE
    def test_indicator_match_should_ignore_surrounding_whitespace(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 'X',
                 'Amount': '5.00', 'Type': ' CR '}]
        result = make_processor(indicator_config()).process_statement(rows)
        assert result['amount'][0] == 5.00

    def test_debit_is_negative_false_leaves_sign_alone(self, make_processor):
        config = indicator_config(amount_config=AmountConfig(
            amount_column='Amount',
            credit_indicator_column='Type',
            credit_indicator_value='CR',
            debit_is_negative=False,
        ))
        rows = [{'Date': '15/01/2024', 'Description': 'X',
                 'Amount': '5.00', 'Type': 'DR'}]
        result = make_processor(config).process_statement(rows)
        assert result['amount'][0] == 5.00

    def test_without_indicator_column_everything_is_a_credit(self, make_processor):
        config = indicator_config(
            amount_config=AmountConfig(amount_column='Amount')
        )
        rows = [{'Date': '15/01/2024', 'Description': 'X', 'Amount': '5.00'}]
        result = make_processor(config).process_statement(rows)
        assert result['amount'][0] == 5.00
        assert bool(result['is_credit'][0]) is True


class TestCleanAmount:
    """_clean_amount is exercised through the pipeline, one value per row."""

    @pytest.fixture
    def parse(self, make_processor):
        def _parse(value, **amount_kwargs):
            config = signed_config(amount_config=AmountConfig(
                amount_column='Amount', signed_amount=True, **amount_kwargs
            ))
            rows = [{'Date': '2024-01-15', 'Description': 'X', 'Amount': value}]
            return make_processor(config).process_statement(rows)['amount'][0]
        return _parse

    @pytest.mark.parametrize('value,expected', [
        ('25.99', 25.99),
        ('-25.99', -25.99),
        (25.99, 25.99),
        (25, 25.0),
        ('€25.99', 25.99),
        ('$25.99', 25.99),
        ('£25.99', 25.99),
        ('1,234.56', 1234.56),
        ('€1,234.56', 1234.56),
        (' 25.99 ', 25.99),
        ('25 . 99', 25.99),
        ('', 0.0),
        ('-', 0.0),
        ('N/A', 0.0),
        ('n/a', 0.0),
        (None, 0.0),
    ])
    def test_values(self, parse, value, expected):
        assert parse(value) == expected

    def test_custom_currency_symbols(self, parse):
        assert parse('EUR25.99', currency_symbols=['EUR']) == 25.99

    def test_european_separators(self, parse):
        assert parse('1.234,56', decimal_separator=',',
                     thousands_separator='.') == 1234.56

    def test_unparseable_value_raises(self, parse):
        with pytest.raises(ValueError):
            parse('twenty five')


# --------------------------------------------------------------------------- #
# description and defaults
# --------------------------------------------------------------------------- #
class TestDescription:

    def test_whitespace_stripped(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': '  TESCO  ',
                 'In': '', 'Out': '1.00'}]
        result = make_processor(split_config()).process_statement(rows)
        assert result['description'][0] == 'TESCO'

    def test_non_string_values_coerced(self, make_processor):
        rows = [{'Date': '15/01/2024', 'Description': 12345,
                 'In': '', 'Out': '1.00'}]
        result = make_processor(split_config()).process_statement(rows)
        assert result['description'][0] == '12345'

    def test_null_becomes_the_string_none(self, make_processor):
        """astype(str) runs before fillna, so NaN becomes 'nan' rather than ''."""
        rows = [{'Date': '15/01/2024', 'Description': None,
                 'In': '', 'Out': '1.00'}]
        result = make_processor(split_config()).process_statement(rows)
        assert result['description'][0] in ('', 'nan', 'None')


class TestDefaults:

    def test_flags_default_to_false(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert not result['is_kids'].any()
        assert not result['is_one_off'].any()

    def test_receipt_id_defaults_to_none(self, make_processor, split_rows):
        result = make_processor(split_config()).process_statement(split_rows)
        assert result['receipt_id'].isna().all()

    def test_config_defaults_applied_to_every_row(self, make_processor, split_rows):
        config = split_config(defaults={'is_kids': True})
        result = make_processor(config).process_statement(split_rows)
        assert result['is_kids'].all()

    def test_config_defaults_do_not_override_parsed_columns(
        self, make_processor, split_rows
    ):
        """is_credit is derived from the data, so a default can't clobber it."""
        config = split_config(defaults={'is_one_off': True})
        result = make_processor(config).process_statement(split_rows)
        assert result['is_credit'].tolist() == [False, True]
        assert result['is_one_off'].all()