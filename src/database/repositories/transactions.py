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
        
    def get_transactions_with_hierarchy(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        party_id: Optional[int] = None,
        account_id: Optional[int] = None,
        upload_id: Optional[int] = None,
        description: Optional[str] = None,
        cleaned_description: Optional[str] = None,
        is_kids: Optional[bool] = None,
        is_one_off: Optional[bool] = None,
        is_credit: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transactions with full party hierarchy information.
        
        Args:
            limit: Maximum number of results
            offset: Pagination offset
            start_date: Filter from date (YYYY-MM-DD)
            end_date: Filter until date (YYYY-MM-DD)
            party_id: Filter by party ID
            account_id: Filter by account ID
            upload_id: Filter by upload ID
            description: Filter by description (substring match)
            cleaned_description: Filter by cleaned description (substring match)
            
        Returns:
            List of transaction dictionaries with hierarchy
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                conditions = []
                params = []
                
                if start_date:
                    conditions.append('t.transaction_date >= ?')
                    params.append(start_date)
                
                if end_date:
                    conditions.append('t.transaction_date <= ?')
                    params.append(end_date)
                
                if party_id:
                    conditions.append('t.party_id = ?')
                    params.append(party_id)
                
                if account_id:
                    conditions.append('t.account_id = ?')
                    params.append(account_id)

                if upload_id:
                    conditions.append('t.upload_id = ?')
                    params.append(upload_id)

                if description:
                    conditions.append('t.description LIKE ?')
                    params.append(f'%{description}%')
                
                if cleaned_description:
                    conditions.append('t.cleaned_description LIKE ?')
                    params.append(f'%{cleaned_description}%')

                if is_kids is not None:
                    conditions.append('t.is_kids = ?')
                    params.append(int(is_kids))

                if is_one_off is not None:
                    conditions.append('t.is_one_off = ?')
                    params.append(int(is_one_off))

                if is_credit is not None:
                    conditions.append('t.is_credit = ?')
                    params.append(int(is_credit))
                
                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                
                query = f'''
                    SELECT 
                        t.*,
                        a.account_name,
                        a.account_type,
                        p.id as party_id,
                        p.name as party_name,
                        tp.id as type_id,
                        tp.type as type_name,
                        sc.id as sub_category_id,
                        sc.sub_category as sub_category_name,
                        c.id as category_id,
                        c.category as category_name,
                        r.id as receipt_id,
                        r.original_filename as receipt_filename,
                        r.vendor as receipt_vendor,
                        r.amount as receipt_amount,
                        r.date as receipt_date
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN types tp ON p.type_id = tp.id
                    LEFT JOIN sub_categories sc ON tp.sub_category_id = sc.id
                    LEFT JOIN categories c ON sc.category_id = c.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    {where_clause}
                    ORDER BY t.transaction_date DESC, t.id DESC
                '''
                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)
                
                if offset:
                    query += ' OFFSET ?'
                    params.append(offset)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get transactions with hierarchy: {e}")
            raise DatabaseError(f"Failed to get transactions: {e}") from e

    def get_transaction_with_hierarchy(self, transaction_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single transaction with full party hierarchy information.
        
        Args:
            transaction_id: The transaction ID
            
        Returns:
            Transaction dictionary with hierarchy or None
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        t.*,
                        a.account_name,
                        a.account_type,
                        p.id as party_id,
                        p.name as party_name,
                        tp.id as type_id,
                        tp.type as type_name,
                        sc.id as sub_category_id,
                        sc.sub_category as sub_category_name,
                        c.id as category_id,
                        c.category as category_name,
                        r.id as receipt_id,
                        r.original_filename as receipt_filename,
                        r.vendor as receipt_vendor,
                        r.amount as receipt_amount,
                        r.date as receipt_date
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN types tp ON p.type_id = tp.id
                    LEFT JOIN sub_categories sc ON tp.sub_category_id = sc.id
                    LEFT JOIN categories c ON sc.category_id = c.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    WHERE t.id = ?
                ''', (transaction_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get transaction with hierarchy for ID {transaction_id}: {e}")
            raise DatabaseError(f"Failed to get transaction: {e}") from e

    def update_transaction(
        self,
        transaction_id: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Update a transaction's fields.
        
        Args:
            transaction_id: The transaction ID
            **kwargs: Fields to update (amount, description, cleaned_description, 
                    is_credit, is_kids, is_one_off, party_id, receipt_id)
                    
        Returns:
            Updated transaction with hierarchy or None if not found
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                # Build update query from provided fields
                allowed_fields = [
                    'amount', 'description', 'cleaned_description',
                    'is_credit', 'is_kids', 'is_one_off', 
                    'party_id', 'receipt_id', 'transaction_date'
                ]
                
                updates = []
                params = []
                
                for field, value in kwargs.items():
                    if field in allowed_fields:
                        updates.append(f"{field} = ?")
                        params.append(value)
                
                if not updates:
                    # No valid updates, just return current transaction
                    return self.get_transaction_with_hierarchy(transaction_id)
                
                params.append(transaction_id)
                query = f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?"
                
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Transaction {transaction_id} not found for update")
                    return None
                
                conn.commit()
                
            # Return updated transaction with hierarchy
            return self.get_transaction_with_hierarchy(transaction_id)
            
        except Exception as e:
            logger.error(f"Failed to update transaction {transaction_id}: {e}")
            raise DatabaseError(f"Failed to update transaction: {e}") from e

    def find_matching_transactions(
        self,
        amount: Optional[float] = None,
        transaction_date: Optional[str] = None,
        party_name: Optional[str] = None,
        amount_tolerance: float = 0.01,
        date_tolerance_days: int = 7,
        include_matched: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find transactions matching given parameters.
        
        Args:
            amount: Amount to match
            transaction_date: Date to match (YYYY-MM-DD)
            party_name: Party name to match (partial match)
            amount_tolerance: Maximum difference in amount
            date_tolerance_days: Maximum difference in days
            include_matched: If True, include transactions with receipts
            limit: Maximum number of results
            
        Returns:
            List of matching transactions with hierarchy
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                conditions = []
                params = []
                
                # Amount matching
                if amount is not None:
                    conditions.append('ABS(t.amount - ?) <= ?')
                    params.extend([amount, amount_tolerance])
                
                # Date matching
                if transaction_date:
                    conditions.append('ABS(julianday(t.transaction_date) - julianday(?)) <= ?')
                    params.extend([transaction_date, date_tolerance_days])
                
                # Party name matching (partial, case-insensitive)
                if party_name:
                    conditions.append('(UPPER(p.name) LIKE UPPER(?) OR UPPER(t.cleaned_description) LIKE UPPER(?))')
                    params.extend([f'%{party_name}%', f'%{party_name}%'])
                
                # Receipt matching
                if not include_matched:
                    conditions.append('t.receipt_id IS NULL')
                
                if not conditions:
                    raise ValueError("At least one search parameter is required")
                
                where_clause = f"WHERE {' AND '.join(conditions)}"
                
                query = f'''
                    SELECT 
                        t.*,
                        a.account_name,
                        a.account_type,
                        p.id as party_id,
                        p.name as party_name,
                        tp.id as type_id,
                        tp.type as type_name,
                        sc.id as sub_category_id,
                        sc.sub_category as sub_category_name,
                        c.id as category_id,
                        c.category as category_name,
                        r.id as receipt_id,
                        r.original_filename as receipt_filename,
                        r.vendor as receipt_vendor
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN types tp ON p.type_id = tp.id
                    LEFT JOIN sub_categories sc ON tp.sub_category_id = sc.id
                    LEFT JOIN categories c ON sc.category_id = c.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    {where_clause}
                    ORDER BY t.transaction_date DESC, t.id DESC
                    LIMIT ?
                '''
                
                params.append(limit)
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to find matching transactions: {e}")
            raise DatabaseError(f"Failed to find matching transactions: {e}") from e

    def link_receipt_to_transaction(
        self,
        transaction_id: int,
        receipt_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Link a receipt to a transaction.
        
        Args:
            transaction_id: The transaction ID
            receipt_id: The receipt ID to link
            
        Returns:
            Updated transaction with hierarchy or None if not found
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                # Verify receipt exists
                cursor.execute('SELECT id FROM receipts WHERE id = ?', (receipt_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Receipt {receipt_id} does not exist")
                
                # Update transaction
                cursor.execute(
                    'UPDATE transactions SET receipt_id = ? WHERE id = ?',
                    (receipt_id, transaction_id)
                )
                
                if cursor.rowcount == 0:
                    return None
                
                conn.commit()
                logger.info(f"Linked receipt {receipt_id} to transaction {transaction_id}")
                
            return self.get_transaction_with_hierarchy(transaction_id)
            
        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to link receipt to transaction: {e}")
            raise DatabaseError(f"Failed to link receipt to transaction: {e}") from e