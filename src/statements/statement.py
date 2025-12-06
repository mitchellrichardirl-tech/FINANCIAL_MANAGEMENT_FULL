from datetime import datetime
from typing import Optional
import logging

import pandas as pd

from src.models.transaction import Transaction
from src.categorizer.transaction_categorizer import TransactionCategorizer

class Statement:
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

    def process_statement(
            self,
            transactions: list[dict]
        ) -> pd.DataFrame:
        """
        Process and categorize transactions from a statement.
        
        Args:
            transactions: List of dictionaries representing transaction rows
        """
        self.transactions = self._preprocess_transactions(transactions)
        self.transactions = self._categorize_transactions()
        self.transactions['account_id'] = int(self.account_id)
        self.transactions['upload_id'] = int(self.upload_id)
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
        # Convert to DataFrame
        df = pd.DataFrame(transactions)
        
        # Convert money columns to numeric, handling empty strings and errors
        df['Money In (€)'] = df['Money In (€)'].fillna(0).astype(str).apply(self.convert_amount_string)
        df['Money Out (€)'] = df['Money Out (€)'].fillna(0).astype(str).apply(self.convert_amount_string)
        
        # Create Amount column (Money Out is already negative)
        df['amount'] = df['Money In (€)'] + df['Money Out (€)']
        
        # Create is_credit boolean column
        df['is_credit'] = df['amount'] > 0
        
        # Convert Date to datetime
        df['transaction_date'] = pd.to_datetime(df['Date'], errors='coerce')
        df.dropna(subset=['transaction_date'], inplace=True)
        
        df['description'] = df['Description'].astype(str).fillna('')

        df['is_kids'] = False
        df['is_one_off'] = False
        df['receipt_id'] = None

        self.transactions = df.loc[:,[
            'transaction_date',
            'amount',
            'description',
            'is_credit',
            'is_kids',
            'is_one_off',
            'receipt_id'
            ]]
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
        categorizations = self.categorizer.categorize(descriptions)
        self.transactions[[
            'cleaned_description',
            'party_id',
            'confidence'
            ]] = pd.DataFrame(categorizations)
        return self.transactions
    
    @staticmethod
    def convert_amount_string(amount: str) -> float:
        result = amount.replace('€', '').replace(',','').replace(' ','').strip()
        if (result == '')|(result == '-'):
            result = 0
        return float(result)