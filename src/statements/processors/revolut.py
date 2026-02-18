from typing import Optional
import pandas as pd

from src.statements.base import StatementProcessor, StatementConfig
from src.statements.configs.revolut import REVOLUT_CURRENT
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class RevolutStatementProcessor(StatementProcessor):
    """
    Custom processor for Revolut statements.
    
    Revolut has some quirks:
    - Multiple currencies in one statement
    - Exchange transactions that should be linked
    - Merchant data in a separate column
    """
    
    def __init__(
        self,
        account_id: int,
        upload_id: int,
        base_currency: str = 'EUR',
        categorizer: Optional[TransactionCategorizer] = None,
    ):
        super().__init__(account_id, upload_id, categorizer)
        self.base_currency = base_currency
    
    @property
    def config(self) -> StatementConfig:
        return REVOLUT_CURRENT
    
    def _filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter to base currency and exclude transfers between pockets."""
        df = super()._filter_rows(df)
        
        # Only process base currency transactions
        if 'Currency' in df.columns:
            non_base = (df['Currency'] != self.base_currency).sum()
            if non_base > 0:
                logger.info(f"Filtering {non_base} non-{self.base_currency} transactions")
            df = df[df['Currency'] == self.base_currency]
        
        return df
    
    def _parse_description(self, df: pd.DataFrame) -> pd.DataFrame:
        """Combine description with merchant info if available."""
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