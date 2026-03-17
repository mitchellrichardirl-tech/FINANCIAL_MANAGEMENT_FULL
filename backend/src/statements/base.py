"""
Statement processing: base classes and configuration dataclasses.

Defines the contract for turning a bank's CSV/Excel export into a normalized
transaction DataFrame. Each bank format is described declaratively by a
`StatementConfig`; the `StatementProcessor` pipeline consumes that config.

Two ways to support a bank:
  - Config only (common) — write a `StatementConfig` in `configs/<bank>.py`,
    the registry wraps it in `ConfigurableStatementProcessor`. No subclassing.
  - Custom processor (rare) — subclass `StatementProcessor` and override
    individual pipeline steps. Needed when the export requires row-level
    transformations config can't express (e.g. Revolut).

Pipeline overview — see `StatementProcessor.process_statement()`:
    raw rows → skip header/footer → validate columns → filter junk
    → parse dates → parse amounts → extract description → defaults
    → categorizer (assign party) → stamp ids → enforce output shape
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

import pandas as pd

from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger
from src.api.utils.errors import AppError, ErrorCode

logger = ContextLogger(__name__)

# TODO: Maybe delete this - I don't think it's actually used
@dataclass
class ColumnMapping:
    """Maps source column(s) to a target field."""
    target: str
    source: str | list[str]  # Single column or multiple for combined fields
    transform: Optional[Callable[[Any], Any]] = None
    default: Any = None


@dataclass
class AmountConfig:
    """
    How to extract a signed amount + credit/debit flag from source columns.

    Banks represent amounts one of three ways. Configure **exactly one**:

      1. **Split columns** — separate Credit and Debit columns, each positive.
         → set `credit_column` and `debit_column`

      2. **Signed column** — one column, sign indicates direction
         (negative = debit).
         → set `amount_column` and `signed_amount=True`

      3. **Amount + indicator** — one unsigned column plus a "CR"/"DR" flag.
         → set `amount_column`, `credit_indicator_column`,
           `credit_indicator_value`

    Output convention regardless of input: debits are negative, credits
    positive (`debit_is_negative=True`). Flip that if your downstream
    expects the opposite.
    """
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
    """
    Declarative description of one bank's statement export format.

    One instance per (bank, account type) combination, living in
    `configs/<bank>.py`. Tells the processor which columns to read,
    how to parse them, and which rows to skip.

    Minimal example::

        StatementConfig(
            bank_name="AIB",
            account_type="Current Account",
            date_config=DateConfig(column="Date", format="%d/%m/%Y"),
            amount_config=AmountConfig(
                credit_column="Credit",
                debit_column="Debit",
            ),
            description_column="Description",
        )

    Attributes:
        bank_name: Human-readable bank name ("AIB", "Revolut").
        account_type: Variant ("Current Account", "Credit Card").
            Combined with bank_name to form `display_name`.
        date_config: Which column holds the date and how to parse it.
        amount_config: Which column(s) hold the amount — see `AmountConfig`
            for the three supported shapes.
        description_column: Source column with the transaction narrative.
        balance_column: Optional running balance. Not used in processing;
            reserved for future reconciliation.
        reference_column: Optional reference/memo column.
        skip_rows_start: Leading rows to discard (title rows, logos).
        skip_rows_end: Trailing rows to discard (totals, disclaimers).
        exclude_patterns: Regexes matched against the description column.
            Matching rows are dropped — use for "OPENING BALANCE" lines etc.
        defaults: Overrides for standard output fields, applied to every
            row from this config. E.g. `{"is_kids": True}` for payments related
            to children.
    """
    bank_name: str
    account_type: str

    date_config: DateConfig
    amount_config: AmountConfig
    description_column: str

    balance_column: Optional[str] = None
    reference_column: Optional[str] = None

    skip_rows_start: int = 0
    skip_rows_end: int = 0

    exclude_patterns: list[str] = field(default_factory=list)
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
        
    @property
    def required_columns(self) -> list[str]:
        """All source columns this config expects to find in the input data."""
        cols = [self.date_config.column, self.description_column]

        amt = self.amount_config
        if amt.credit_column and amt.debit_column:
            cols.extend([amt.credit_column, amt.debit_column])
        elif amt.amount_column:
            cols.append(amt.amount_column)
            if amt.credit_indicator_column:
                cols.append(amt.credit_indicator_column)

        # Dedupe while preserving order
        seen = set()
        return [c for c in cols if c and not (c in seen or seen.add(c))]

    @property
    def display_name(self) -> str:
        return f"{self.bank_name} {self.account_type}"
    
@dataclass
class ProcessingWarning:
    """Non-fatal issue the user should be told about."""
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {'code': self.code, 'message': self.message, 'details': self.details}

class StatementProcessor(ABC):
    """
    Abstract pipeline for parsing statement rows into normalized transactions.

    The pipeline lives in `process_statement()`. Each stage is a separate
    private method, so subclasses can override one step without
    reimplementing the whole thing.

    **You usually don't subclass this.** If the bank's format fits a
    `StatementConfig`, the registry uses `ConfigurableStatementProcessor`
    automatically. Subclass only for banks that need transformations
    config can't express — row merging, multi-currency normalization, etc.

    Instance state:
        account_id: Stamped onto every output row.
        upload_id: Stamped onto every output row.
        categorizer: Assigns `party_id` and `confidence` per description.
            Injectable for testing; defaults to a fresh TransactionCategorizer.
        transactions: Output DataFrame — populated by `process_statement()`.
        warnings: Non-fatal issues (e.g. some dates unparseable) collected
            during processing. The caller should surface these to the user.

    Class attributes:
        OUTPUT_COLUMNS: Exact column set the repository layer expects.
            `_finalize_columns()` guarantees this shape.
        _DATE_FORMAT_FALLBACKS: Formats tried when the configured date
            format fails. Ordered roughly by likelihood for Irish/EU banks.
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

    _DATE_FORMAT_FALLBACKS = [
        '%Y-%m-%dT%H:%M:%SZ',    # 2022-10-13T01:02:03Z   ← the format in your logs
        '%Y-%m-%dT%H:%M:%S%z',   # 2022-10-13T01:02:03+00:00
        '%Y-%m-%dT%H:%M:%S',     # 2022-10-13T01:02:03
        '%Y-%m-%d',              # 2022-10-13
        '%d/%m/%Y', '%d/%m/%y',  # European
        '%m/%d/%Y', '%m/%d/%y',  # US
        '%d-%m-%Y', '%d.%m.%Y',
        '%Y/%m/%d',
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
        self.warnings: list[ProcessingWarning] = []

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
        Run the full pipeline on raw statement rows.

        Args:
            transactions: Rows as dicts, keys = source file column headers.
                Typically produced by `utils/tabular_files/readers.py`.

        Returns:
            DataFrame with exactly `OUTPUT_COLUMNS`, one row per transaction.
            Also stored on `self.transactions`.

        Raises:
            AppError (INVALID_FORMAT): Required columns are missing, or no
                dates are parseable by any known format. The error's `details`
                dict is structured for direct display — the frontend's
                ColumnMismatchPanel consumes it.

        Side effects:
            Appends `ProcessingWarning` entries to `self.warnings` for
            partial failures (e.g. 5 of 200 dates unparseable → those rows
            are dropped, a warning is recorded). Caller must surface these.
        """
        logger.info(
            f"Processing {self.config.display_name} statement: "
            f"{len(transactions)} rows for account {self.account_id}"
        )

        df = pd.DataFrame(transactions)

        # Skip configured rows BEFORE validating columns — headers/footers
        # won't affect the column set, but doing it first matches the
        # original behaviour order.
        if self.config.skip_rows_start > 0:
            df = df.iloc[self.config.skip_rows_start:]
        if self.config.skip_rows_end > 0:
            df = df.iloc[:-self.config.skip_rows_end]

        # Validate columns before any processing touches them
        self._validate_required_columns(df)

        df = self._filter_rows(df)
        df = self._parse_dates(df)
        df = self._parse_amounts(df)
        df = self._parse_description(df)
        df = self._apply_defaults(df)
        df = self._categorize(df)

        df['account_id'] = int(self.account_id)
        df['upload_id'] = int(self.upload_id)

        self.transactions = self._finalize_columns(df)

        logger.info(
            f"Processing complete: {len(self.transactions)} transactions"
        )
        return self.transactions

    def _validate_required_columns(self, df: pd.DataFrame) -> None:
        """
        Verify all columns required by the config exist in the input data.

        Raises AppError with details about what's missing and what was found,
        so the user can tell whether they picked the wrong account or the
        wrong file.
        """
        required = self.config.required_columns
        actual = list(df.columns)
        missing = [c for c in required if c not in actual]

        if not missing:
            logger.debug(
                f"Column check passed for {self.config.display_name}: "
                f"all {len(required)} required columns present"
            )
            return

        logger.warning(
            f"Column mismatch for {self.config.display_name}: "
            f"missing={missing}, found={actual}"
        )

        raise AppError(
            code=ErrorCode.INVALID_FORMAT,
            message=(
                f"This file doesn't match the '{self.config.display_name}' "
                f"statement format. "
                f"Missing column(s): {', '.join(missing)}. "
                f"File contains: {', '.join(actual) or '(no columns)'}."
            ),
            status_code=422,
            entity='Statement',
            details={
                'statement_format': self.config.display_name,
                'account_id': self.account_id,
                'missing_columns': missing,
                'required_columns': required,
                'found_columns': actual,
            },
        )

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
        date_cfg = self.config.date_config
        col = date_cfg.column
        rows_before = len(df)

        sample_values = df[col].dropna().astype(str).head(3).tolist()
        logger.debug(
            f"Parsing dates: column={col!r}, format={date_cfg.format!r}, "
            f"dayfirst={date_cfg.dayfirst} | samples: {sample_values}"
        )

        parsed, used_format = self._attempt_date_parse(df[col], date_cfg)
        df['transaction_date'] = parsed

        cfg_label = date_cfg.format or f'auto(dayfirst={date_cfg.dayfirst})'
        if used_format != cfg_label:
            logger.warning(
                f"Configured format {date_cfg.format!r} didn't match this file. "
                f"Used {used_format!r} instead."
            )

        invalid_mask = df['transaction_date'].isna()
        invalid_count = int(invalid_mask.sum())

        if invalid_count > 0:
            invalid_samples = (
                df.loc[invalid_mask, col].dropna().astype(str).head(5).tolist()
            )
            logger.warning(
                f"Dropping {invalid_count}/{rows_before} rows with unparseable "
                f"dates (best format: {used_format!r}) | samples: {invalid_samples}"
            )

            # ── This is the bit that was missing ──
            self.warnings.append(ProcessingWarning(
                code='DATES_UNPARSEABLE',
                message=(
                    f"{invalid_count} of {rows_before} rows were skipped because "
                    f"the date in column '{col}' couldn't be parsed."
                ),
                details={
                    'dropped': invalid_count,
                    'total': rows_before,
                    'column': col,
                    'format_used': used_format,
                    'sample_values': invalid_samples,
                },
            ))

            df = df.dropna(subset=['transaction_date'])

        return df


    def _attempt_date_parse(
        self,
        series: pd.Series,
        date_cfg: DateConfig,
    ) -> tuple[pd.Series, str]:
        """
        Best-effort date parsing across multiple format candidates.

        Tries the configured format, then every fallback, and keeps whichever
        parses the **most** rows. Only short-circuits on 100% — a format that
        parses 80% might still lose to one that parses 95%, so we try them all.

        Why this is lenient: banks change export formats without warning, and
        users often open files in Excel first which silently reformats dates.
        A fuzzy parse + warning beats failing the whole import.

        Returns:
            Tuple of (parsed series, label of winning format). The label is
            for logging and for the `ProcessingWarning` shown to the user.

        Raises:
            AppError (INVALID_FORMAT): Zero rows parsed by any candidate.
        """
        total = int(series.notna().sum())
        if total == 0:
            return pd.to_datetime(series, errors='coerce'), 'n/a (empty)'

        # Build an ordered list of (label, to_datetime kwargs) to try.
        cfg_label = date_cfg.format or f'auto(dayfirst={date_cfg.dayfirst})'
        attempts: list[tuple[str, dict]] = [
            (cfg_label, {'format': date_cfg.format, 'dayfirst': date_cfg.dayfirst}),
        ]

        # dayfirst=True mangles ISO-8601 when auto-detecting — try without it too.
        if date_cfg.format is None and date_cfg.dayfirst:
            attempts.append(('auto(dayfirst=False)', {'format': None, 'dayfirst': False}))

        # pandas >= 2.0 has a flexible ISO8601 parser — the try/except
        # in the loop below handles older versions gracefully.
        attempts.append(('ISO8601', {'format': 'ISO8601'}))

        best_fmt = date_cfg.format or 'auto-detected'

        for fmt in self._DATE_FORMAT_FALLBACKS:
            if fmt != date_cfg.format:
                attempts.append((fmt, {'format': fmt}))

        best_parsed: pd.Series | None = None
        best_valid = -1
        best_label = cfg_label

        for label, kwargs in attempts:
            try:
                parsed = pd.to_datetime(series, errors='coerce', **kwargs)
            except (ValueError, TypeError):
                continue

            valid = int(parsed.notna().sum())
            logger.debug(f"Date format {label!r}: {valid}/{total} parsed")

            if valid > best_valid:
                best_parsed, best_valid, best_label = parsed, valid, label

            if valid == total:
                return parsed, label          # perfect match — done

        if best_valid <= 0:
            sample = series.dropna().astype(str).head(3).tolist()
            raise AppError(
                code=ErrorCode.INVALID_FORMAT,
                message=(
                    f"Could not parse any dates in column '{date_cfg.column}'. "
                    f"Sample values: {sample}."
                ),
                status_code=422,
                entity='Statement',
                field=date_cfg.column,
                details={
                    'column': date_cfg.column,
                    'sample_values': sample,
                    'formats_tried': [lbl for lbl, _ in attempts],
                },
            )

        return best_parsed, best_label

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
        
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default
                
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
    Config-driven processor with no custom logic. The default.

    Used for any bank whose export is fully described by a `StatementConfig`.
    The registry (`statements/registry.py`) instantiates this automatically
    when a config is registered without a custom processor — you rarely
    construct it by hand.
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