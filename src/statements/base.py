from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

import pandas as pd

from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


@dataclass
class ColumnMapping:
    """Maps source column(s) to a target field."""
    target: str
    source: str | list[str]  # Single column or multiple for combined fields
    transform: Optional[Callable[[Any], Any]] = None
    default: Any = None


@dataclass
class AmountConfig:
    """Configuration for parsing transaction amounts."""
    # Option 1: Separate credit/debit columns
    credit_column: Optional[str] = None
    debit_column: Optional[str] = None
    
    # Option 2: Single amount column with sign or indicator
    amount_column: Optional[str] = None
    credit_indicator_column: Optional[str] = None
    credit_indicator_value: Optional[str] = None
    
    # Option 3: Single amount column, negative = debit
    signed_amount: bool = False
    
    # Common settings
    currency_symbols: list[str] = field(default_factory=lambda: ['€', '$', '£'])
    decimal_separator: str = '.'
    thousands_separator: str = ','
    debit_is_negative: bool = True  # Convention: debits stored as negative


@dataclass
class DateConfig:
    """Configuration for parsing dates."""
    column: str
    format: Optional[str] = None  # None = let pandas infer
    dayfirst: bool = True  # European format by default


@dataclass
class StatementConfig:
    """Complete configuration for a bank statement format."""
    bank_name: str
    account_type: str  # e.g., 'current', 'credit_card', 'savings'
    
    # Column mappings
    date_config: DateConfig
    amount_config: AmountConfig
    description_column: str
    
    # Optional columns that may exist in the statement
    balance_column: Optional[str] = None
    reference_column: Optional[str] = None
    
    # Rows to skip (headers, footers, summary rows)
    skip_rows_start: int = 0
    skip_rows_end: int = 0
    
    # Filters to exclude non-transaction rows
    exclude_patterns: list[str] = field(default_factory=list)
    
    # Default values for output fields
    defaults: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration."""
        amt = self.amount_config
        has_split = amt.credit_column and amt.debit_column
        has_single = amt.amount_column is not None
        
        if not has_split and not has_single:
            raise ValueError(
                "AmountConfig must specify either credit_column/debit_column "
                "or amount_column"
            )


class StatementProcessor(ABC):
    """
    Abstract base class for processing bank statements.
    
    Subclasses can either:
    1. Just provide a config (most cases) - use ConfigurableStatementProcessor
    2. Override methods for custom logic (complex cases)
    """
    
    # Standard output columns expected by the database
    OUTPUT_COLUMNS = [
        'transaction_date',
        'amount', 
        'description',
        'is_credit',
        'is_kids',
        'is_one_off',
        'receipt_id',
        'cleaned_description',
        'party_id',
        'confidence',
        'account_id',
        'upload_id'
    ]

    def __init__(
        self,
        account_id: int,
        upload_id: int,
        categorizer: Optional[TransactionCategorizer] = None,
    ):
        self.account_id = account_id
        self.upload_id = upload_id
        self.categorizer = categorizer or TransactionCategorizer()
        self.transactions: Optional[pd.DataFrame] = None
        
        logger.debug(
            f"Initialized {self.__class__.__name__}: "
            f"account_id={account_id}, upload_id={upload_id}"
        )

    @property
    @abstractmethod
    def config(self) -> StatementConfig:
        """Return the configuration for this statement type."""
        pass

    def process_statement(self, transactions: list[dict]) -> pd.DataFrame:
        """
        Main entry point: process raw statement data into categorized transactions.
        
        Args:
            transactions: List of dictionaries representing statement rows
            
        Returns:
            DataFrame with standardized, categorized transactions
        """
        logger.info(
            f"Processing {self.config.bank_name} {self.config.account_type} statement: "
            f"{len(transactions)} rows for account {self.account_id}"
        )
        
        df = pd.DataFrame(transactions)
        
        # Skip configured rows
        if self.config.skip_rows_start > 0:
            df = df.iloc[self.config.skip_rows_start:]
        if self.config.skip_rows_end > 0:
            df = df.iloc[:-self.config.skip_rows_end]
        
        df = self._filter_rows(df)
        df = self._parse_dates(df)
        df = self._parse_amounts(df)
        df = self._parse_description(df)
        df = self._apply_defaults(df)
        df = self._categorize(df)
        
        # Add metadata
        df['account_id'] = int(self.account_id)
        df['upload_id'] = int(self.upload_id)
        
        # Ensure output columns exist and are ordered
        self.transactions = self._finalize_columns(df)
        
        logger.info(
            f"Processing complete: {len(self.transactions)} transactions"
        )
        return self.transactions

    def _filter_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove non-transaction rows based on configured patterns."""
        initial_count = len(df)
        
        for pattern in self.config.exclude_patterns:
            mask = df[self.config.description_column].str.contains(
                pattern, case=False, na=False, regex=True
            )
            df = df[~mask]
        
        filtered = initial_count - len(df)
        if filtered > 0:
            logger.debug(f"Filtered out {filtered} non-transaction rows")
            
        return df

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse transaction dates."""
        date_cfg = self.config.date_config
        
        df['transaction_date'] = pd.to_datetime(
            df[date_cfg.column],
            format=date_cfg.format,
            dayfirst=date_cfg.dayfirst,
            errors='coerce'
        )
        
        invalid_dates = df['transaction_date'].isna().sum()
        if invalid_dates > 0:
            logger.warning(f"Dropping {invalid_dates} rows with invalid dates")
            df = df.dropna(subset=['transaction_date'])
        
        return df

    def _parse_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse transaction amounts and determine credit/debit."""
        amt_cfg = self.config.amount_config
        
        if amt_cfg.credit_column and amt_cfg.debit_column:
            df = self._parse_split_amounts(df, amt_cfg)
        elif amt_cfg.signed_amount:
            df = self._parse_signed_amount(df, amt_cfg)
        else:
            df = self._parse_single_amount(df, amt_cfg)
        
        return df

    def _parse_split_amounts(
        self, df: pd.DataFrame, cfg: AmountConfig
    ) -> pd.DataFrame:
        """Handle statements with separate credit/debit columns."""
        credit = df[cfg.credit_column].apply(self._clean_amount)
        debit = df[cfg.debit_column].apply(self._clean_amount)
        
        if cfg.debit_is_negative:
            df['amount'] = credit - debit
        else:
            df['amount'] = credit + debit
            
        df['is_credit'] = credit > 0
        return df

    def _parse_signed_amount(
        self, df: pd.DataFrame, cfg: AmountConfig
    ) -> pd.DataFrame:
        """Handle statements with a single signed amount column."""
        df['amount'] = df[cfg.amount_column].apply(self._clean_amount)
        df['is_credit'] = df['amount'] > 0
        return df

    def _parse_single_amount(
        self, df: pd.DataFrame, cfg: AmountConfig
    ) -> pd.DataFrame:
        """Handle statements with amount + credit indicator."""
        df['amount'] = df[cfg.amount_column].apply(self._clean_amount)
        
        if cfg.credit_indicator_column:
            df['is_credit'] = (
                df[cfg.credit_indicator_column] == cfg.credit_indicator_value
            )
            # Apply sign based on credit/debit
            if cfg.debit_is_negative:
                df.loc[~df['is_credit'], 'amount'] *= -1
        else:
            # Assume all positive, user must handle sign elsewhere
            df['is_credit'] = True
            
        return df

    def _clean_amount(self, value: Any) -> float:
        """Convert a currency string to float."""
        if pd.isna(value):
            return 0.0
            
        if isinstance(value, (int, float)):
            return float(value)
            
        s = str(value).strip()
        
        # Remove currency symbols
        for symbol in self.config.amount_config.currency_symbols:
            s = s.replace(symbol, '')
        
        # Handle thousands/decimal separators
        s = s.replace(self.config.amount_config.thousands_separator, '')
        s = s.replace(self.config.amount_config.decimal_separator, '.')
        s = s.replace(' ', '')
        
        if s in ('', '-', 'N/A', 'n/a'):
            return 0.0
            
        return float(s)

    def _parse_description(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and clean description."""
        df['description'] = (
            df[self.config.description_column]
            .astype(str)
            .fillna('')
            .str.strip()
        )
        return df

    def _apply_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply default values for standard fields."""
        defaults = {
            'is_kids': False,
            'is_one_off': False,
            'receipt_id': None,
            **self.config.defaults
        }
        
        for field, default in defaults.items():
            if field not in df.columns:
                df[field] = default
                
        return df

    def _categorize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Categorize transactions using the categorizer."""
        descriptions = df['description'].tolist()
        logger.debug(f"Categorizing {len(descriptions)} transactions")
        
        categorizations = self.categorizer.categorize(descriptions)
        
        df[['cleaned_description', 'party_id', 'confidence']] = pd.DataFrame(
            categorizations, index=df.index
        )
        
        return df

    def _finalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns exist and select output columns."""
        for col in self.OUTPUT_COLUMNS:
            if col not in df.columns:
                df[col] = None
                
        return df[self.OUTPUT_COLUMNS].reset_index(drop=True)


class ConfigurableStatementProcessor(StatementProcessor):
    """
    A statement processor that's fully driven by configuration.
    
    Use this when no custom logic is needed—just provide a config.
    """
    
    def __init__(
        self,
        statement_config: StatementConfig,
        account_id: int,
        upload_id: int,
        categorizer: Optional[TransactionCategorizer] = None,
    ):
        self._config = statement_config
        super().__init__(account_id, upload_id, categorizer)
    
    @property
    def config(self) -> StatementConfig:
        return self._config