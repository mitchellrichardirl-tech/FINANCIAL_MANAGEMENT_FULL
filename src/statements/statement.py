from datetime import datetime
from typing import Optional

import pandas as pd

from src.models.transaction import Transaction
from src.categorizer.transaction_categorizer import TransactionCategorizer
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class Statement:
    """Processes bank statement data into categorized transactions."""

    def __init__(
        self,
        account_id: int,
        upload_id: int,
        categorizer: Optional[TransactionCategorizer] = None,
    ):
        self.required_columns = {
            "transaction_date": datetime,
            "amount": float,
            "description": str,
            "is_credit": bool
        }
        self.optional_columns = {
            "is_kids": bool,
            "is_one_off": bool,
            "receipt_id": int
        }
        self.account_id = account_id
        self.upload_id = upload_id
        self.categorizer = categorizer or TransactionCategorizer()
        self.transactions: Optional[pd.DataFrame] = None

        logger.debug(
            f"Initialized Statement: account_id={account_id}, upload_id={upload_id}"
        )

    def process_statement(
        self,
        transactions: list[dict]
    ) -> pd.DataFrame:
        """
        Process and categorize transactions from a statement.
        
        Args:
            transactions: List of dictionaries representing transaction rows
        """
        logger.info(
            f"Processing statement: {len(transactions)} rows "
            f"for account {self.account_id}, upload {self.upload_id}"
        )

        self.transactions = self._preprocess_transactions(transactions)
        self.transactions = self._categorize_transactions()
        self.transactions['account_id'] = int(self.account_id)
        self.transactions['upload_id'] = int(self.upload_id)

        logger.info(
            f"Statement processing complete: {len(self.transactions)} transactions "
            f"for account {self.account_id}"
        )
        return self.transactions

    def _preprocess_transactions(
        self,
        transactions: list[dict]
    ) -> pd.DataFrame:
        """
        Preprocess transaction data from CSV format.
        
        Args:
            transactions: List of dictionaries representing transaction rows
            
        Returns:
            pandas DataFrame with preprocessed data
        """
        logger.debug(f"Preprocessing {len(transactions)} transaction rows")

        df = pd.DataFrame(transactions)

        initial_rows = len(df)
        logger.debug(f"Input columns: {list(df.columns)}")

        # Convert money columns to numeric
        df['Money In (€)'] = df['Money In (€)'].fillna(0).astype(str).apply(self.convert_amount_string)
        df['Money Out (€)'] = df['Money Out (€)'].fillna(0).astype(str).apply(self.convert_amount_string)

        df['amount'] = df['Money In (€)'] + df['Money Out (€)']
        df['is_credit'] = df['amount'] > 0

        # Convert dates, dropping unparseable rows
        df['transaction_date'] = pd.to_datetime(df['Date'], errors='coerce')
        dropped = df['transaction_date'].isna().sum()
        df.dropna(subset=['transaction_date'], inplace=True)

        if dropped > 0:
            logger.warning(
                f"Dropped {dropped}/{initial_rows} rows with invalid dates"
            )

        df['description'] = df['Description'].astype(str).fillna('')
        df['is_kids'] = False
        df['is_one_off'] = False
        df['receipt_id'] = None

        self.transactions = df.loc[:, [
            'transaction_date',
            'amount',
            'description',
            'is_credit',
            'is_kids',
            'is_one_off',
            'receipt_id'
        ]]

        credit_count = self.transactions['is_credit'].sum()
        debit_count = len(self.transactions) - credit_count

        logger.debug(
            f"Preprocessed {len(self.transactions)} transactions "
            f"(credits={credit_count}, debits={debit_count})"
        )
        return self.transactions

    def _categorize_transactions(self) -> pd.DataFrame:
        """
        Categorize transactions using the provided TransactionCategorizer.
        
        Returns:
            pandas DataFrame with categorized transactions
        """
        if self.transactions is None:
            raise ValueError("Transactions have not been preprocessed yet.")

        descriptions = self.transactions['description'].tolist()
        logger.debug(f"Categorizing {len(descriptions)} transaction descriptions")

        categorizations = self.categorizer.categorize(descriptions)
        self.transactions[[
            'cleaned_description',
            'party_id',
            'confidence'
        ]] = pd.DataFrame(categorizations)

        return self.transactions

    @staticmethod
    def convert_amount_string(amount: str) -> float:
        """Convert a currency string to float."""
        result = amount.replace('€', '').replace(',', '').replace(' ', '').strip()
        if result in ('', '-'):
            result = 0
        return float(result)