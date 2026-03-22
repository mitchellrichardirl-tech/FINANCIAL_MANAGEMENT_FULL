"""
Custom statement processor for Revolut exports.

Revolut's CSV exports differ from standard bank statements in ways that
the declarative `StatementConfig` can't fully express:

    - Multiple currencies appear in a single export file.
    - Merchant names live in a separate column from the description.
    - Exchange/transfer transactions between pockets may need filtering.

This processor extends `StatementProcessor` with overrides for row
filtering and description parsing. All other pipeline stages (date
parsing, amount parsing, categorization, etc.) use the base
implementation driven by `REVOLUT_CURRENT` config.
"""

from typing import Optional
import pandas as pd

from src.statements.base import StatementProcessor, StatementConfig
from src.statements.configs.revolut import REVOLUT_CURRENT
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class RevolutStatementProcessor(StatementProcessor):
    """Revolut-specific statement processor.

    Adds currency filtering and merchant-name extraction on top of the
    standard pipeline. Only transactions in the `base_currency` are
    kept; foreign-currency rows are dropped with a log message.

    Attributes:
        base_currency: ISO 4217 currency code to keep (e.g. "EUR").
            Rows with a different `Currency` column value are discarded.
    """

    def __init__(
        self,
        account_id: int,
        upload_id: int,
        base_currency: str = 'EUR',
        categorizer: Optional[TransactionCategorizer] = None,
    ):
        """Initialize with a base currency for filtering.

        Args:
            account_id: FK to `accounts.id` — stamped on every output row.
            upload_id: FK to `uploads.id` — the import batch.
            base_currency: ISO 4217 code. Only transactions in this
                currency are imported. Defaults to "EUR".
            categorizer: Optional custom `TransactionCategorizer`. If
                None, uses the default.
        """
        super().__init__(account_id, upload_id, categorizer)
        self.base_currency = base_currency

    @property
    def config(self) -> StatementConfig:
        """Return the Revolut statement configuration."""
        return REVOLUT_CURRENT

    def _filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to base currency after applying standard exclude patterns.

        Calls the parent `_filter_rows()` first (which handles
        `exclude_patterns` from the config), then removes any rows
        whose `Currency` column doesn't match `self.base_currency`.

        If the `Currency` column is absent, no currency filtering is
        applied — the file may be a single-currency export.

        Args:
            df: DataFrame after header/footer trimming.

        Returns:
            Filtered DataFrame with only base-currency transactions.
        """
        df = super()._filter_rows(df)

        # Only process base currency transactions
        if 'Currency' in df.columns:
            non_base = (df['Currency'] != self.base_currency).sum()
            if non_base > 0:
                logger.info(f"Filtering {non_base} non-{self.base_currency} transactions")
            df = df[df['Currency'] == self.base_currency]

        return df

    def _parse_description(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build description from the description column plus merchant name.

        Calls the parent `_parse_description()` first (which reads and
        cleans the configured description column), then appends the
        `Merchant` column value if present and non-empty, separated by
        " - ".

        This gives the categorizer a richer string to match against
        (e.g. "Card Payment - Tesco Express" rather than just
        "Card Payment").

        Args:
            df: DataFrame with at least the description column populated.

        Returns:
            DataFrame with `description` column enriched with merchant
            info where available.
        """
        df = super()._parse_description(df)

        # Revolut often has merchant name in a separate column
        if 'Merchant' in df.columns:
            df['Merchant'].fillna('', inplace=True)
            df['description'] = df.apply(
                lambda row: f"{row['description']} - {row['Merchant']}"
                if pd.notna(row.get('Merchant')) and row.get('Merchant', '').strip()
                else row['description'],
                axis=1
            )

        return df
