from typing import Optional, Dict, List, Any
import logging
import sqlite3
import pandas as pd

from src.database.connection import get_manager, DatabaseError
from src.models.transaction import Transaction

logger = logging.getLogger(__name__)

class TransactionRepository:
    """Repository for transaction CRUD operations"""
    
    def __init__(self):
        self.db = get_manager()

    def add_transaction(self, transaction: Transaction):
        """Add a new financial transaction"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions 
                    (transaction_date, amount, description, cleaned_description,
                               is_credit, is_kids, is_one_off, account_id,
                               upload_id, party_id, receipt_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction.transaction_date, transaction.amount,
                      transaction.description, transaction.cleaned_description,
                      transaction.is_credit, transaction.is_kids,
                      transaction.is_one_off, transaction.account_id,
                      transaction.upload_id, transaction.party_id,
                      transaction.receipt_id))
                conn.commit()
                transaction_id = cursor.lastrowid
                return transaction_id
        except Exception as e:
            logger.error(f"Failed to add transaction: {e}")
            raise DatabaseError(f"Failed to add transaction: {e}") from e

    def bulk_add_transactions(self, df: pd.DataFrame) -> List[int]:
        """
        Bulk insert transactions from a pandas DataFrame
        
        Args:
            df: DataFrame with columns matching transaction fields:
                - transaction_date
                - amount
                - description
                - cleaned_description (optional)
                - is_credit (optional, default False)
                - is_kids (optional, default False)
                - is_one_off (optional, default False)
                - account_id (optional)
                - upload_id (optional)
                - party_id (optional)
                - receipt_id (optional)
        
        Returns:
            List of inserted transaction IDs
        """
        try:
            # Validate required columns
            required_columns = ['transaction_date', 'amount', 'description']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Create a copy and fill optional columns with defaults
            df_copy = df.copy()
            df_copy['transaction_date'] = pd.to_datetime(df_copy['transaction_date']).dt.strftime('%Y-%m-%d')
            optional_defaults = {
                'cleaned_description': None,
                'is_credit': False,
                'is_kids': False,
                'is_one_off': False,
                'account_id': None,
                'upload_id': None,
                'party_id': None,
                'receipt_id': None
            }
            
            for col, default in optional_defaults.items():
                if col not in df_copy.columns:
                    df_copy[col] = default
            
            # Prepare data as list of tuples in correct order
            columns_order = [
                'transaction_date', 'amount', 'description', 'cleaned_description',
                'is_credit', 'is_kids', 'is_one_off', 'account_id',
                'upload_id', 'party_id', 'receipt_id'
            ]
            
            data = [tuple(row) for row in df_copy[columns_order].values]
            
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT INTO transactions 
                    (transaction_date, amount, description, cleaned_description,
                     is_credit, is_kids, is_one_off, account_id,
                     upload_id, party_id, receipt_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)
                conn.commit()
                cursor.execute('SELECT MAX(id) FROM transactions')
                max_id = cursor.fetchone()[0]
                # Get the IDs of inserted rows
                transaction_ids = list(range(max_id - len(data) + 1, max_id + 1))
                
                logger.info(f"Successfully inserted {len(data)} transactions")
                return transaction_ids
                
        except ValueError as e:
            logger.error(f"Invalid DataFrame structure: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to bulk add transactions: {e}")
            raise DatabaseError(f"Failed to bulk add transactions: {e}") from e

    def bulk_add_transactions_from_objects(self, transactions: List[Transaction]) -> List[int]:
        """
        Bulk insert transactions from a list of Transaction objects
        
        Args:
            transactions: List of Transaction objects
        
        Returns:
            List of inserted transaction IDs
        """
        try:
            data = [
                (t.transaction_date, t.amount, t.description, t.cleaned_description,
                 t.is_credit, t.is_kids, t.is_one_off, t.account_id,
                 t.upload_id, t.party_id, t.receipt_id)
                for t in transactions
            ]
            
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.executemany('''
                    INSERT INTO transactions 
                    (transaction_date, amount, description, cleaned_description,
                     is_credit, is_kids, is_one_off, account_id,
                     upload_id, party_id, receipt_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)
                conn.commit()
                
                first_id = cursor.lastrowid - len(data) + 1
                transaction_ids = list(range(first_id, first_id + len(data)))
                
                logger.info(f"Successfully inserted {len(data)} transactions")
                return transaction_ids
                
        except Exception as e:
            logger.error(f"Failed to bulk add transactions: {e}")
            raise DatabaseError(f"Failed to bulk add transactions: {e}") from e
        
    def get_transactions(self, limit: Optional[int] = None):
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT t.*,
                               a.name as account_name,
                               p.name as related_party_name,
                               r.filename as receipt_filename
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p on t.party_id = p.id
                    LEFT JOIN receipts r on t.receipt_id = r.id
                    ORDER BY t.transaction_date DESC
                '''
                if limit:
                    query += f' LIMIT {limit}'

                cursor.execute(query)
                rows = cursor.fetchall()
                transactions = [Transaction(**dict(row)) for row in rows]
                return transactions
        except Exception as e:
                logger.error(f"Failed to get transaction: {e}")
                raise DatabaseError(f"Failed to get transaction: {e}") from e
        
    def get_transaction_by_id(self, transaction_id: int) -> Optional[Transaction]:
        """
        Get a single transaction by its ID
        
        Args:
            transaction_id: The ID of the transaction to retrieve
        
        Returns:
            Transaction object if found, None otherwise
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*,
                        a.name as account_name,
                        p.name as related_party_name,
                        r.filename as receipt_filename
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    WHERE t.id = ?
                ''', (transaction_id,))
                
                row = cursor.fetchone()
                if row:
                    return Transaction(**dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Failed to get transaction by id {transaction_id}: {e}")
            raise DatabaseError(f"Failed to get transaction by id: {e}") from e

    def find_receipt_match_candidates(
        self, 
        amount: float, 
        transaction_date: str,
        amount_tolerance: float = 0.01,
        date_tolerance_days: int = 7,
        include_matched: bool = False
    ) -> List[Transaction]:
        """
        Find candidate transactions that could match a receipt.
        
        Args:
            amount: The receipt amount to match
            transaction_date: The receipt date (YYYY-MM-DD format)
            amount_tolerance: Maximum difference in amount (default: 0.01 = 1 cent)
            date_tolerance_days: Maximum difference in days (default: 7)
            include_matched: If True, include transactions that already have receipts
        
        Returns:
            List of Transaction objects that match the criteria,
            ordered by closest date first
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                base_query = '''
                    SELECT t.*,
                        a.name as account_name,
                        p.name as related_party_name,
                        r.filename as receipt_filename
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    WHERE ABS(t.amount - ?) <= ?
                    AND ABS(julianday(t.transaction_date) - julianday(?)) <= ?
                '''
                
                if not include_matched:
                    base_query += ' AND t.receipt_id IS NULL'
                
                base_query += '''
                    ORDER BY ABS(julianday(t.transaction_date) - julianday(?)) ASC,
                            ABS(t.amount - ?) ASC
                '''
                
                cursor.execute(base_query, (
                    amount, amount_tolerance, 
                    transaction_date, date_tolerance_days,
                    transaction_date, amount
                ))
                
                rows = cursor.fetchall()
                transactions = [Transaction(**dict(row)) for row in rows]
                
                logger.debug(
                    f"Found {len(transactions)} candidate transactions for "
                    f"amount={amount}, date={transaction_date}"
                )
                return transactions
                
        except Exception as e:
            logger.error(f"Failed to find receipt match candidates: {e}")
            raise DatabaseError(f"Failed to find receipt match candidates: {e}") from e