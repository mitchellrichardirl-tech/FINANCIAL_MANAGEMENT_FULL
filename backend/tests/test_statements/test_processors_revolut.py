"""
Tests for src/statements/processors/revolut.py.

RevolutStatementProcessor overrides two pipeline stages - `_filter_rows`
(currency filtering) and `_parse_description` (merchant enrichment) - and
inherits everything else from StatementProcessor. These tests focus on the
two overrides plus the interaction with the REVOLUT_CURRENT config; the
shared pipeline behaviour is covered in test_base.py.

The categorizer is stubbed, so no database is involved.
"""
import pandas as pd
import pytest

from src.statements.base import StatementProcessor
from src.statements.configs.revolut import REVOLUT_CURRENT
from src.statements.processors.revolut import RevolutStatementProcessor


NUMERIC_MERCHANT = pytest.mark.xfail(
    reason="_parse_description calls .strip() on the raw Merchant value, so a "
           "merchant pandas typed as a number (e.g. a CSV cell of '7874') "
           "raises AttributeError and kills the whole import - backlog",
    strict=True,
)


class StubCategorizer:
    def __init__(self):
        self.seen = None

    def categorize(self, descriptions):
        self.seen = list(descriptions)
        return [
            {'cleaned_description': d, 'party_id': 1, 'confidence': 90}
            for d in descriptions
        ]


@pytest.fixture
def categorizer():
    return StubCategorizer()


@pytest.fixture
def make_processor(categorizer):
    def _make(base_currency='EUR', account_id=1, upload_id=2):
        return RevolutStatementProcessor(
            account_id=account_id,
            upload_id=upload_id,
            base_currency=base_currency,
            categorizer=categorizer,
        )
    return _make


@pytest.fixture
def processor(make_processor):
    return make_processor()


def row(**overrides):
    """A Revolut export row. Columns match REVOLUT_CURRENT."""
    base = {
        'Type': 'CARD_PAYMENT',
        'Started Date': '2024-01-15 10:30:00',
        'Description': 'Card Payment',
        'Amount': '-25.99',
        'Currency': 'EUR',
        'Balance': '1000.00',
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #
class TestConstruction:

    def test_uses_the_revolut_config(self, processor):
        assert processor.config is REVOLUT_CURRENT
        assert processor.config.display_name == 'Revolut current'

    def test_base_currency_defaults_to_eur(self, categorizer):
        processor = RevolutStatementProcessor(
            account_id=1, upload_id=2, categorizer=categorizer
        )
        assert processor.base_currency == 'EUR'

    def test_base_currency_is_configurable(self, make_processor):
        assert make_processor(base_currency='GBP').base_currency == 'GBP'

    def test_inherits_the_standard_pipeline(self, processor):
        assert isinstance(processor, StatementProcessor)

    def test_ids_are_stored(self, make_processor):
        processor = make_processor(account_id=7, upload_id=8)
        assert (processor.account_id, processor.upload_id) == (7, 8)


# --------------------------------------------------------------------------- #
# currency filtering
# --------------------------------------------------------------------------- #
class TestCurrencyFiltering:

    def test_keeps_only_base_currency(self, processor):
        rows = [
            row(Description='EUR one', Currency='EUR'),
            row(Description='USD one', Currency='USD'),
            row(Description='GBP one', Currency='GBP'),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['EUR one']

    def test_respects_a_non_default_base_currency(self, make_processor):
        rows = [
            row(Description='EUR one', Currency='EUR'),
            row(Description='GBP one', Currency='GBP'),
        ]
        result = make_processor(base_currency='GBP').process_statement(rows)
        assert result['description'].tolist() == ['GBP one']

    def test_no_currency_column_means_no_filtering(self, processor):
        rows = [
            {k: v for k, v in row(Description='A').items() if k != 'Currency'},
            {k: v for k, v in row(Description='B').items() if k != 'Currency'},
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['A', 'B']

    def test_currency_match_is_case_sensitive(self, processor):
        rows = [row(Description='lower', Currency='eur'),
                row(Description='upper', Currency='EUR')]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['upper']

    def test_null_currency_rows_are_dropped(self, processor):
        rows = [row(Description='null', Currency=None),
                row(Description='good', Currency='EUR')]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['good']

    def test_config_exclude_patterns_still_applied(self, processor):
        """The override calls super() first, so exclude_patterns keep working."""
        rows = [
            row(Description='Top-Up by card'),
            row(Description='Balance migration to new account'),
            row(Description='Card Payment'),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['Card Payment']

    def test_exclude_patterns_and_currency_filter_combine(self, processor):
        rows = [
            row(Description='Top-Up by card', Currency='EUR'),
            row(Description='Card Payment', Currency='USD'),
            row(Description='Card Payment', Currency='EUR'),
        ]
        result = processor.process_statement(rows)
        assert len(result) == 1


# --------------------------------------------------------------------------- #
# merchant enrichment
# --------------------------------------------------------------------------- #
class TestMerchantEnrichment:

    def test_merchant_appended_to_description(self, processor):
        rows = [row(Description='Card Payment', Merchant='Tesco Express')]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment - Tesco Express'

    def test_enriched_description_reaches_the_categorizer(self, processor, categorizer):
        rows = [row(Description='Card Payment', Merchant='Tesco Express')]
        processor.process_statement(rows)
        assert categorizer.seen == ['Card Payment - Tesco Express']

    def test_no_merchant_column_leaves_description_alone(self, processor):
        result = processor.process_statement([row(Description='Card Payment')])
        assert result['description'][0] == 'Card Payment'

    def test_empty_merchant_leaves_description_alone(self, processor):
        rows = [row(Description='Card Payment', Merchant='')]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment'

    def test_whitespace_merchant_leaves_description_alone(self, processor):
        rows = [row(Description='Card Payment', Merchant='   ')]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment'

    def test_null_merchant_leaves_description_alone(self, processor):
        rows = [row(Description='Card Payment', Merchant=None)]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment'

    def test_mixed_rows_enriched_individually(self, processor):
        rows = [
            row(Description='Card Payment', Merchant='Tesco'),
            row(Description='Transfer', Merchant=None),
            row(Description='Card Payment', Merchant='Lidl'),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == [
            'Card Payment - Tesco', 'Transfer', 'Card Payment - Lidl'
        ]

    def test_merchant_whitespace_is_not_stripped_from_the_output(self, processor):
        """The guard strips before testing, but the value is appended raw."""
        rows = [row(Description='Card Payment', Merchant=' Tesco ')]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment -  Tesco '

    @NUMERIC_MERCHANT
    def test_numeric_merchant_is_coerced_not_fatal(self, processor):
        rows = [row(Description='Card Payment', Merchant=12345)]
        result = processor.process_statement(rows)
        assert result['description'][0] == 'Card Payment - 12345'

    @NUMERIC_MERCHANT
    def test_one_numeric_merchant_does_not_kill_the_whole_import(self, processor):
        rows = [
            row(Description='A', Merchant='Tesco'),
            row(Description='B', Merchant=12345),
        ]
        assert len(processor.process_statement(rows)) == 2


# --------------------------------------------------------------------------- #
# interaction between the two overrides
# --------------------------------------------------------------------------- #
class TestOverridesTogether:

    def test_merchant_enrichment_applies_after_currency_filtering(self, processor):
        rows = [
            row(Description='Card Payment', Currency='USD', Merchant='Amazon US'),
            row(Description='Card Payment', Currency='EUR', Merchant='Tesco'),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['Card Payment - Tesco']

    def test_filtered_frame_is_not_a_view(self, processor):
        """Enrichment writes to a frame that row filtering already sliced."""
        rows = [
            row(Description='Card Payment', Currency='USD', Merchant='Amazon'),
            row(Description='Card Payment', Currency='EUR', Merchant='Tesco'),
            row(Description='Card Payment', Currency='EUR', Merchant=None),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == [
            'Card Payment - Tesco', 'Card Payment'
        ]

    def test_index_is_reset_after_filtering(self, processor):
        rows = [
            row(Description='Card Payment', Currency='USD'),
            row(Description='Card Payment', Currency='EUR'),
        ]
        assert list(processor.process_statement(rows).index) == [0]


# --------------------------------------------------------------------------- #
# the rest of the pipeline still works through this subclass
# --------------------------------------------------------------------------- #
class TestInheritedPipeline:

    def test_output_shape(self, processor):
        result = processor.process_statement([row()])
        assert list(result.columns) == StatementProcessor.OUTPUT_COLUMNS

    def test_signed_amounts(self, processor):
        rows = [
            row(Description='Spend', Amount='-25.99'),
            row(Description='Refund', Amount='100.00'),
        ]
        result = processor.process_statement(rows)
        assert result['amount'].tolist() == [-25.99, 100.00]
        assert result['is_credit'].tolist() == [False, True]

    def test_revolut_datetime_format(self, processor):
        result = processor.process_statement(
            [row(**{'Started Date': '2024-01-15 10:30:00'})]
        )
        assert result['transaction_date'][0] == pd.Timestamp('2024-01-15 10:30:00')

    def test_ids_stamped(self, make_processor):
        result = make_processor(account_id=7, upload_id=8).process_statement([row()])
        assert result['account_id'].tolist() == [7]
        assert result['upload_id'].tolist() == [8]

    def test_missing_required_column_raises(self, processor):
        from src.api.utils.errors import AppError

        rows = [{k: v for k, v in row().items() if k != 'Amount'}]
        with pytest.raises(AppError) as exc:
            processor.process_statement(rows)
        assert exc.value.details['missing_columns'] == ['Amount']

    def test_balance_column_is_not_required(self, processor):
        rows = [{k: v for k, v in row().items() if k != 'Balance'}]
        assert len(processor.process_statement(rows)) == 1

    def test_unparseable_date_warns_and_drops(self, processor):
        rows = [
            row(Description='good'),
            row(Description='bad', **{'Started Date': 'not a date'}),
        ]
        result = processor.process_statement(rows)
        assert result['description'].tolist() == ['good']
        assert processor.warnings[0].code == 'DATES_UNPARSEABLE'