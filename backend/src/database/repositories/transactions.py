"""
Repository for transaction data access.

Provides the `TransactionRepository` class, which handles CRUD, bulk
operations, filtered queries, and receipt-linking against the
`transactions` table.

Return types vary by method:
    - Write operations and simple reads return `Transaction` model
      instances.
    - Hierarchy-aware reads (anything that joins through
      parties → types → sub_categories → categories) return plain dicts,
      since the extra columns don't fit the `Transaction` model.
"""

from typing import Optional, Dict, List, Any
import pandas as pd

from src.database.connection import get_manager
from src.database.errors import (
    DatabaseError,
    TransactionRuleError,
    _NOW,
    SOURCE_SPLIT,
    SOURCE_GENERATED,
    DELETED_REASON_CASCADE,
    DELETED_REASON_USER,
    RESTORABLE_REASONS,
    _RESTORE_HELP
    )
from src.models.transaction import Transaction
from src.utils.logging import ContextLogger
from src.api.utils.errors import not_found

logger = ContextLogger(__name__)


class TransactionRepository:
    """Data-access layer for the `transactions` table.

    Covers single-row and bulk inserts, filtered listing with full
    category hierarchy joins, partial updates, and receipt-matching
    queries used by the receipt-linking workflow.

    Attributes:
        db: The default `ConnectionManager` instance.
    """

    def __init__(self):
        """Initialize with the default connection manager.

        Raises:
            DatabaseError: If the connection manager has not been
                initialized via `connection.init()` / `init_app()`.
        """
        self.db = get_manager()

    def add_transaction(self, transaction: Transaction) -> int:
        """Insert a single transaction from a `Transaction` model instance.

        Args:
            transaction: Populated `Transaction` model. `party_id` and
                `upload_id` are required by the schema.

        Returns:
            The `id` of the newly created transaction row.

        Raises:
            DatabaseError: On foreign-key violations, constraint failures,
                or any other database error.
        """
        logger.debug(
            f"Adding transaction: {transaction.description[:50]}... "
            f"| amount={transaction.amount}"
        )

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions 
                    (transaction_date, amount, description, cleaned_description,
                        is_credit, is_kids, is_one_off, account_id,
                        upload_id, party_id, receipt_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction.transaction_date, transaction.amount,
                    transaction.description, transaction.cleaned_description,
                    transaction.is_credit, transaction.is_kids,
                    transaction.is_one_off, transaction.account_id,
                    transaction.upload_id, transaction.party_id,
                    transaction.receipt_id
                ))
                transaction_id = cursor.lastrowid

            logger.info(f"Added transaction {transaction_id}")
            return transaction_id

        except Exception as e:
            logger.error(f"Failed to add transaction: {e}")
            raise DatabaseError(f"Failed to add transaction: {e}") from e

    def bulk_add_transactions(self, df: pd.DataFrame) -> List[int]:
        """Bulk insert transactions from a pandas DataFrame.

        Validates that required columns are present, fills missing
        optional columns with defaults, normalises dates to ISO format,
        and inserts all rows in a single transaction.

        Args:
            df: DataFrame with at least `transaction_date`, `amount`,
                and `description` columns. Optional columns
                (`cleaned_description`, `is_credit`, `is_kids`,
                `is_one_off`, `account_id`, `upload_id`, `party_id`,
                `receipt_id`) default to None/False if absent.

        Returns:
            List of auto-generated `id` values for the inserted rows.

        Raises:
            ValueError: If any required columns are missing.
            DatabaseError: On any database failure (entire batch is
                rolled back).

        Note:
            IDs are inferred from `MAX(id)` after insert, which assumes
            no concurrent inserts to the same table.
        """
        logger.info(f"Bulk inserting {len(df)} transactions from DataFrame")

        try:
            required_columns = ['transaction_date', 'amount', 'description']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.warning(f"Missing required columns: {missing_columns}")
                raise ValueError(f"Missing required columns: {missing_columns}")

            df_copy = df.copy()
            df_copy['transaction_date'] = pd.to_datetime(
                df_copy['transaction_date']
            ).dt.strftime('%Y-%m-%d')

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

                cursor.execute('SELECT MAX(id) FROM transactions')
                max_id = cursor.fetchone()[0]
                transaction_ids = list(range(max_id - len(data) + 1, max_id + 1))

            logger.info(f"Bulk inserted {len(data)} transactions (ids {transaction_ids[0]}-{transaction_ids[-1]})")
            return transaction_ids

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to bulk add transactions: {e}")
            raise DatabaseError(f"Failed to bulk add transactions: {e}") from e

    def bulk_add_transactions_from_objects(self, transactions: List[Transaction]) -> List[int]:
        """Bulk insert transactions from a list of `Transaction` objects.

        Similar to `bulk_add_transactions()` but accepts model instances
        instead of a DataFrame. Preferred for statement-import pipelines
        that already construct `Transaction` objects.

        Args:
            transactions: List of `Transaction` model instances.

        Returns:
            List of auto-generated `id` values for the inserted rows.
            Empty list if `transactions` is empty.

        Raises:
            DatabaseError: On any database failure (entire batch is
                rolled back).

        Note:
            IDs are inferred from `lastrowid`, which assumes no
            concurrent inserts to the same table.
        """
        if not transactions:
            logger.debug("No transactions to insert")
            return []

        logger.info(f"Bulk inserting {len(transactions)} transaction objects")

        try:
            data = [
                (
                    t.transaction_date, t.amount, t.description, t.cleaned_description,
                    t.is_credit, t.is_kids, t.is_one_off, t.account_id,
                    t.upload_id, t.party_id, t.receipt_id
                )
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

                first_id = cursor.lastrowid - len(data) + 1
                transaction_ids = list(range(first_id, first_id + len(data)))

            logger.info(
                f"Bulk inserted {len(data)} transactions "
                f"(ids {transaction_ids[0]}-{transaction_ids[-1]})"
            )
            return transaction_ids

        except Exception as e:
            logger.error(f"Failed to bulk add transactions: {e}")
            raise DatabaseError(f"Failed to bulk add transactions: {e}") from e

    def get_transactions(
        self,
        limit: Optional[int] = None,
        include_deleted: bool = False
    ) -> List[Transaction]:
        """Fetch transactions as `Transaction` model instances.
        Joins to `accounts`, `parties`, and `receipts` to populate
        `account_name`, `related_party_name`, and `receipt_filename`.
        Ordered by date descending (most recent first).
        Soft-deleted transactions (`deleted_at IS NOT NULL`) are excluded
        unless `include_deleted` is True.
        Args:
            limit: Maximum rows to return. None for all.
            include_deleted: If True, include soft-deleted transactions.
                Defaults to False.
        Returns:
            List of `Transaction` instances. Empty list if the table
            is empty.
        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT t.*,
                        a.account_name as account_name,
                        p.name as related_party_name,
                        r.original_filename as receipt_filename
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                '''
                if not include_deleted:
                    query += ' WHERE t.deleted_at IS NULL'
                query += ' ORDER BY t.transaction_date DESC'
                if limit:
                    query += ' LIMIT ?'
                    cursor.execute(query, (limit,))
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                transactions = [Transaction(**dict(row)) for row in rows]
                logger.debug(
                    f"Retrieved {len(transactions)} transactions "
                    f"(include_deleted={include_deleted})"
                )
                return transactions

        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            raise DatabaseError(f"Failed to get transactions: {e}") from e

    def get_transaction_by_id(
        self,
        transaction_id: int,
        include_deleted: bool = False
    ) -> Optional[Transaction]:
        """Fetch a single transaction by primary key.
        Joins to `accounts`, `parties`, and `receipts` for context
        fields. Returns None for soft-deleted transactions unless
        `include_deleted` is True.
        Args:
            transaction_id: The transaction's `id` column value.
            include_deleted: If True, return the row even if it has been
                soft-deleted. Defaults to False.
        Returns:
            A `Transaction` instance, or None if no match.
        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
                    SELECT t.*,
                        a.account_name as account_name,
                        p.name as related_party_name,
                        r.original_filename as receipt_filename
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    WHERE t.id = ?
                '''
                if not include_deleted:
                    query += ' AND t.deleted_at IS NULL'
                cursor.execute(query, (transaction_id,))
                row = cursor.fetchone()
                if not row:
                    logger.debug(f"Transaction {transaction_id} not found")
                    return None
                return Transaction(**dict(row))
        except Exception as e:
            logger.error(f"Failed to get transaction {transaction_id}: {e}")
            raise DatabaseError(f"Failed to get transaction: {e}") from e

    def find_receipt_match_candidates(
        self,
        amount: float,
        transaction_date: str,
        amount_tolerance: float = 0.01,
        date_tolerance_days: int = 7,
        include_matched: bool = False
    ) -> List[Transaction]:
        """Find transactions that could match a given receipt.

        Used by the receipt-linking workflow. Searches for transactions
        whose amount and date are within the given tolerances, optionally
        excluding transactions that already have a receipt linked.

        Results are ordered by date proximity first, then amount
        proximity, so the best match appears first.

        Args:
            amount: Receipt amount to match against.
            transaction_date: Receipt date in YYYY-MM-DD format.
            amount_tolerance: Maximum absolute difference in amount.
                Defaults to 0.01.
            date_tolerance_days: Maximum difference in days between
                receipt date and transaction date. Defaults to 7.
            include_matched: If True, include transactions that already
                have a receipt linked. Defaults to False.

        Returns:
            List of `Transaction` instances ordered by match quality
            (closest first). Empty list if no candidates found.

        Raises:
            DatabaseError: On query failure.
        """
        logger.debug(
            f"Finding receipt match candidates: amount={amount}, "
            f"date={transaction_date}, tolerance={amount_tolerance}"
        )

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                base_query = '''
                    ...
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    LEFT JOIN parties p ON t.party_id = p.id
                    LEFT JOIN receipts r ON t.receipt_id = r.id
                    WHERE t.deleted_at IS NULL
                    AND ABS(t.amount - ?) <= ?
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
                    f"Found {len(transactions)} candidates for "
                    f"amount={amount}, date={transaction_date}"
                )
                return transactions

        except Exception as e:
            logger.error(f"Failed to find receipt match candidates: {e}")
            raise DatabaseError(f"Failed to find receipt match candidates: {e}") from e

    # Joins shared by the page query and the count query. Declared once so the
    # two can never disagree about what they're counting.
    #
    # Every join is on an INTEGER PRIMARY KEY, so none of them can multiply
    # rows — COUNT(*) over this FROM clause equals COUNT(*) over `transactions`
    # alone. SQLite's omit-LEFT-JOIN optimisation also drops any join whose
    # table isn't referenced in the WHERE clause, so carrying all six in the
    # count query costs nothing.
    _HIERARCHY_FROM = '''
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN parties p ON t.party_id = p.id
        LEFT JOIN types tp ON p.type_id = tp.id
        LEFT JOIN sub_categories sc ON tp.sub_category_id = sc.id
        LEFT JOIN categories c ON sc.category_id = c.id
        LEFT JOIN receipts r ON t.receipt_id = r.id
    '''

    def _build_hierarchy_filters(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        party_id: Optional[int] = None,
        account_id: Optional[int] = None,
        upload_id: Optional[int] = None,
        description: Optional[str] = None,
        cleaned_description: Optional[str] = None,
        is_kids: Optional[bool] = None,
        is_one_off: Optional[bool] = None,
        is_credit: Optional[bool] = None,
        category_id: Optional[int] = None,
        sub_category_id: Optional[int] = None,
        type_id: Optional[int] = None,
        has_receipt: Optional[bool] = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        deleted_reason: Optional[str] = None,
    ) -> tuple[str, List[Any]]:
        """Build the WHERE clause shared by the page and count queries.
        Single source of truth for transaction filtering. If the two queries
        built their conditions separately they would eventually drift, and a
        paginated response would report a total for a different result set
        than the one it returned.
        Keyword-only by design: these are always passed as `**filters`.
        Returns:
            Tuple of (where_clause, params). `where_clause` is an empty string
            when nothing is filtered.
        """
        conditions: List[str] = []
        params: List[Any] = []
        # Soft-delete filter. Must be expressed literally as `deleted_at IS NULL`
        # for SQLite to use the partial index idx_transactions_active_date.
        if deleted_only:
            conditions.append('t.deleted_at IS NOT NULL')
        elif not include_deleted:
            conditions.append('t.deleted_at IS NULL')
        if deleted_reason:
            conditions.append('t.deleted_reason = ?')
            params.append(deleted_reason)
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
        if category_id:
            conditions.append('c.id = ?')
            params.append(category_id)
        if sub_category_id:
            conditions.append('sc.id = ?')
            params.append(sub_category_id)
        if type_id:
            conditions.append('tp.id = ?')
            params.append(type_id)
        if has_receipt is not None:
            conditions.append(
                't.receipt_id IS NOT NULL' if has_receipt else 't.receipt_id IS NULL'
            )
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, params
    
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
        is_credit: Optional[bool] = None,
        category_id: Optional[int] = None,
        sub_category_id: Optional[int] = None,
        type_id: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
        has_receipt: Optional[bool] = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        deleted_reason: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch transactions with full category hierarchy and optional filters.

        The primary query method for the transaction listing UI. Joins
        through the full chain (accounts, parties → types →
        sub_categories → categories, receipts) and supports filtering
        at every level plus sortable columns.

        All filter arguments are optional and ANDed together. Returns
        dicts rather than `Transaction` instances because the joined
        columns don't fit the model.

        Args:
            limit: Maximum rows to return. None for all.
            offset: Rows to skip for pagination. Defaults to 0.
            start_date: Include transactions on or after this date
                (YYYY-MM-DD).
            end_date: Include transactions on or before this date
                (YYYY-MM-DD).
            party_id: Filter by exact party.
            account_id: Filter by exact account.
            upload_id: Filter by import batch.
            description: Substring match on raw description.
            cleaned_description: Substring match on cleaned description.
            is_kids: Filter by kids flag.
            is_one_off: Filter by one-off flag.
            is_credit: Filter by credit/debit direction.
            category_id: Filter by category (via hierarchy join).
            sub_category_id: Filter by subcategory (via hierarchy join).
            type_id: Filter by type (via hierarchy join).
            sort_by: Column name to sort by. Must be in the whitelist
                (e.g. "transaction_date", "amount", "party_name").
                Defaults to "transaction_date". Unrecognised values
                fall back to the default.
            sort_dir: "asc" or "desc". Defaults to "desc".
            has_receipt: Filter by presence of receipt.
            include_deleted: If True, include soft-deleted transactions
                alongside live ones. Defaults to False.
            deleted_only: If True, return *only* soft-deleted
                transactions (for a recycle-bin view). Takes precedence
                over `include_deleted`. Defaults to False.
        Returns:
            List of transaction dicts, each including `account_name`,
            `account_type`, `party_name`, `type_name`,
            `sub_category_name`, `category_name`, and receipt fields.
            Empty list if no matches.

        Raises:
            DatabaseError: On query failure.
        """

        # Whitelist of allowed sort columns to prevent SQL injection
        # Keys are the API field names, values are the actual SQL column references
        SORTABLE_COLUMNS = {
            'transaction_date': 't.transaction_date',
            'amount': 't.amount',
            'description': 't.description',
            'cleaned_description': 't.cleaned_description',
            'is_credit': 't.is_credit',
            'is_kids': 't.is_kids',
            'is_one_off': 't.is_one_off',
            'account_name': 'a.account_name',
            'party_name': 'p.name',
            'type_name': 'tp.type',
            'sub_category_name': 'sc.sub_category',
            'category_name': 'c.category',
            'has_receipt': 't.receipt_id IS NOT NULL'
        }

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                where_clause, params = self._build_hierarchy_filters(
                    start_date=start_date,
                    end_date=end_date,
                    party_id=party_id,
                    account_id=account_id,
                    upload_id=upload_id,
                    description=description,
                    cleaned_description=cleaned_description,
                    is_kids=is_kids,
                    is_one_off=is_one_off,
                    is_credit=is_credit,
                    category_id=category_id,
                    sub_category_id=sub_category_id,
                    type_id=type_id,
                    has_receipt=has_receipt,
                    include_deleted=include_deleted,
                    deleted_only=deleted_only,
                    deleted_reason=deleted_reason,
                )
                sort_column = SORTABLE_COLUMNS.get(sort_by, 't.transaction_date')
                sort_direction = 'ASC' if sort_dir == 'asc' else 'DESC'
                order_clause = f"ORDER BY {sort_column} {sort_direction}, t.id DESC"
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
                    {self._HIERARCHY_FROM}
                    {where_clause}
                    {order_clause}
                '''
                # SQLite requires LIMIT before OFFSET. `LIMIT -1` means "no limit",
                # which is the only way to offset into an unbounded result set.
                if limit is not None:
                    query += ' LIMIT ?'
                    params.append(limit)
                    if offset:
                        query += ' OFFSET ?'
                        params.append(offset)
                elif offset:
                    query += ' LIMIT -1 OFFSET ?'
                    params.append(offset)
                cursor.execute(query, params)
                rows = cursor.fetchall()
                logger.debug(
                    f"Retrieved {len(rows)} transactions with hierarchy "
                    f"(offset={offset}, limit={limit}, sort={sort_by} {sort_dir})"
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get transactions with hierarchy: {e}")
            raise DatabaseError(f"Failed to get transactions: {e}") from e

    def count_transactions_with_hierarchy(self, **filters) -> int:
        """Count transactions matching the same filters as the page query.
        Takes the same filter keyword arguments as
        `get_transactions_with_hierarchy()`. Pagination and sort arguments
        (`limit`, `offset`, `sort_by`, `sort_dir`) are *not* accepted — they
        don't affect the count, and passing them raises `TypeError` rather than
        being silently ignored.
        Deliberately `**filters` rather than a duplicated signature: the route
        forwards the same dict to both methods, so adding a new filter to
        `_build_hierarchy_filters()` wires it into the count automatically.
        Returns:
            Number of matching transactions, ignoring limit/offset.
        Raises:
            TypeError: If an unrecognised filter name is passed.
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                where_clause, params = self._build_hierarchy_filters(**filters)
                cursor.execute(
                    f'SELECT COUNT(*) {self._HIERARCHY_FROM} {where_clause}',
                    params,
                )
                total = cursor.fetchone()[0]
                logger.debug(f"Counted {total} transactions with hierarchy")
                return total
        except Exception as e:
            logger.error(f"Failed to count transactions with hierarchy: {e}")
            raise DatabaseError(f"Failed to count transactions: {e}") from e

    def get_transaction_with_hierarchy(
        self,
        transaction_id: int,
        include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single transaction with full category hierarchy.
        Same joins as `get_transactions_with_hierarchy()` but for one
        row. Used after updates to return the refreshed state to the
        caller.
        Args:
            transaction_id: Primary key of the transaction.
            include_deleted: If True, return the row even if it has been
                soft-deleted. Defaults to False. Used by
                `delete_transaction()` / `restore_transaction()` to read
                back rows the default filter would hide.
        Returns:
            Transaction dict with all hierarchy and receipt fields,
            or None if the transaction doesn't exist (or is deleted and
            `include_deleted` is False).
        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                query = '''
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
                '''
                if not include_deleted:
                    query += ' AND t.deleted_at IS NULL'
                cursor.execute(query, (transaction_id,))
                row = cursor.fetchone()
                if not row:
                    logger.debug(f"Transaction {transaction_id} not found")
                    return None
                return dict(row)
        except Exception as e:
            logger.error(f"Failed to get transaction {transaction_id} with hierarchy: {e}")
            raise DatabaseError(f"Failed to get transaction: {e}") from e

    def update_transaction(
        self,
        transaction_id: int,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on a transaction.

        Accepts arbitrary keyword arguments but only applies fields
        from an internal allowlist: `amount`, `description`,
        `cleaned_description`, `is_credit`, `is_kids`, `is_one_off`,
        `party_id`, `receipt_id`, `transaction_date`. Unrecognised
        keys are silently ignored.

        Args:
            transaction_id: Primary key of the transaction to update.
            **kwargs: Field names and new values. Only allowlisted
                fields are applied.

        Returns:
            The updated transaction dict with full hierarchy, or None
            if the transaction doesn't exist.

        Raises:
            DatabaseError: On any database failure including FK
                violations.

        Notes:
            allowed_fields must never be allowed to contain deleted_at,
            deleted_reason, source_transaction_id, or source_relationship.
            These must never be user updatable fields.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                allowed_fields = [
                    'amount', 'description', 'cleaned_description',
                    'is_credit', 'is_kids', 'is_one_off',
                    'party_id', 'receipt_id', 'transaction_date'
                ]

                updates = []
                params = []
                updated_fields = []

                for field, value in kwargs.items():
                    if field in allowed_fields:
                        updates.append(f"{field} = ?")
                        params.append(value)
                        updated_fields.append(field)

                if not updates:
                    logger.debug(f"No valid fields to update for transaction {transaction_id}")
                    return self.get_transaction_with_hierarchy(transaction_id)

                params.append(transaction_id)
                query = (
                    f"UPDATE transactions SET {', '.join(updates)} "
                    f"WHERE id = ? AND deleted_at IS NULL"
                )

                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Transaction {transaction_id} not found for update")
                    return None

            logger.info(f"Updated transaction {transaction_id}: {updated_fields}")
            return self.get_transaction_with_hierarchy(transaction_id)

        except Exception as e:
            logger.error(f"Failed to update transaction {transaction_id}: {e}")
            raise DatabaseError(f"Failed to update transaction: {e}") from e

    def bulk_update_transactions(
        self,
        transaction_ids: List[int],
        **kwargs
    ) -> Dict[str, Any]:
        """Apply the same field updates to multiple transactions.

        Useful for batch operations like "mark selected as kids" or
        "reassign party". Uses a single `UPDATE ... WHERE id IN (...)`
        statement for efficiency.

        Args:
            transaction_ids: Primary keys of the transactions to update.
            **kwargs: Field names and new values. Only allowlisted
                fields are applied (same list as `update_transaction()`).

        Returns:
            Dict with:
                - `updated_count`: Number of rows actually changed.
                - `updated_ids`: The input ID list (echoed back).
                - `fields_updated`: List of field names that were applied.

            Returns `{'updated_count': 0, 'updated_ids': []}` if
            `transaction_ids` is empty or no valid fields were provided.

        Raises:
            DatabaseError: On any database failure (entire batch is
                rolled back).

        Notes:
            allowed_fields must never be allowed to contain deleted_at,
            deleted_reason, source_transaction_id, or source_relationship.
            These must never be user updatable fields.
        """
        if not transaction_ids:
            return {'updated_count': 0, 'updated_ids': []}

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                allowed_fields = [
                    'amount', 'description', 'cleaned_description',
                    'is_credit', 'is_kids', 'is_one_off',
                    'party_id', 'receipt_id', 'transaction_date'
                ]

                updates = []
                params = []
                updated_fields = []

                for field, value in kwargs.items():
                    if field in allowed_fields:
                        updates.append(f"{field} = ?")
                        params.append(value)
                        updated_fields.append(field)

                if not updates:
                    logger.debug("No valid fields to update in bulk operation")
                    return {'updated_count': 0, 'updated_ids': []}

                # Create placeholders for the IN clause
                placeholders = ','.join('?' * len(transaction_ids))
                params.extend(transaction_ids)

                query = f"""
                    UPDATE transactions 
                    SET {', '.join(updates)} 
                    WHERE id IN ({placeholders})
                      AND deleted_at IS NULL
                """

                cursor.execute(query, params)
                updated_count = cursor.rowcount

            logger.info(
                f"Bulk updated {updated_count} transactions "
                f"(requested {len(transaction_ids)}): {updated_fields}"
            )

            return {
                'updated_count': updated_count,
                'updated_ids': transaction_ids,
                'fields_updated': updated_fields
            }

        except Exception as e:
            logger.error(f"Failed to bulk update transactions: {e}")
            raise DatabaseError(f"Failed to bulk update transactions: {e}") from e

    # SQLite's default SQLITE_MAX_VARIABLE_NUMBER is 999 on older builds
    # (32766 since 3.32). Chunk well below the conservative limit.
    _MAX_SQL_VARIABLES = 900
    @staticmethod
    def _chunked(items: List[Any], size: int):
        """Yield successive `size`-length slices of `items`."""
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def delete_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """Soft-delete a transaction, cascading to its generated children.
        Sets `deleted_at` and `deleted_reason = 'user'`. Any live child
        with `source_relationship = 'generated'` (e.g. a cash lodgement
        derived from an ATM withdrawal) is soft-deleted in the same
        database transaction with `deleted_reason = 'cascade'`, so that
        restoring the parent can later restore exactly those rows and no
        others.
        Children the user had already deleted by hand keep their original
        `deleted_reason = 'user'` and are not touched.
        Args:
            transaction_id: Primary key of the transaction to delete.
        Returns:
            Dict with:
                - `deleted`: True if a live transaction was soft-deleted.
                  False if it doesn't exist or was already deleted.
                - `transaction_id`: Echoed back.
                - `cascaded_ids`: IDs of generated children also deleted.
                  The caller should remove these from the UI too.
        Raises:
            TransactionRuleError: If the transaction is a split child
                (`source_relationship = 'split'`). Deleting one line item
                of a split would silently break amount conservation;
                unsplit the source transaction instead.
            DatabaseError: On any database failure (all or nothing).
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                row = self._fetch_delete_state(cursor, transaction_id)
                if row is None or row['deleted_at'] is not None:
                    logger.debug(
                        f"Transaction {transaction_id} not found or already deleted"
                    )
                    return {
                        'deleted': False,
                        'transaction_id': transaction_id,
                        'cascaded_ids': []
                    }
                if row['source_relationship'] == SOURCE_SPLIT:
                    raise TransactionRuleError(
                        f"Transaction {transaction_id} is one line of a split and "
                        f"cannot be deleted on its own. Unsplit transaction "
                        f"{row['source_transaction_id']} instead."
                    )
                # Collect before updating: once the parent is marked deleted
                # we can still find children, but capturing IDs up front keeps
                # the response honest if the predicate ever changes.
                cascaded_ids = self._live_generated_children(cursor, transaction_id)
                cursor.execute(f'''
                    UPDATE transactions
                    SET deleted_at = {_NOW},
                        deleted_reason = ?
                    WHERE id = ? AND deleted_at IS NULL
                ''', (DELETED_REASON_USER, transaction_id))
                if cascaded_ids:
                    cursor.execute(f'''
                        UPDATE transactions
                        SET deleted_at = {_NOW},
                            deleted_reason = ?
                        WHERE source_transaction_id = ?
                          AND source_relationship = ?
                          AND deleted_at IS NULL
                    ''', (DELETED_REASON_CASCADE, transaction_id, SOURCE_GENERATED))
            logger.info(
                f"Soft-deleted transaction {transaction_id}"
                + (f" (cascaded to {cascaded_ids})" if cascaded_ids else "")
            )
            return {
                'deleted': True,
                'transaction_id': transaction_id,
                'cascaded_ids': cascaded_ids
            }
        except TransactionRuleError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete transaction {transaction_id}: {e}")
            raise DatabaseError(f"Failed to delete transaction: {e}") from e
        
    def bulk_delete_transactions(self, transaction_ids: List[int]) -> Dict[str, Any]:
        """Soft-delete multiple transactions, cascading to generated children.
        Atomic: if any requested ID is a split child, nothing is deleted.
        A half-applied bulk delete is worse than a rejected one — the user
        can unsplit and retry, but can't easily tell which of fifty rows
        went through.
        Ordering matters. Explicit IDs are marked `'user'` first; the
        cascade pass then runs against the remainder, so a child the user
        explicitly selected is recorded as `'user'` (and will survive a
        later restore of its parent) rather than `'cascade'`.
        Args:
            transaction_ids: Primary keys to delete. Duplicates collapsed.
        Returns:
            Dict with:
                - `deleted_count`: Rows soft-deleted with reason 'user'.
                - `deleted_ids`: Which ones.
                - `cascaded_ids`: Generated children also deleted.
                - `skipped_ids`: Requested IDs that didn't exist or were
                  already deleted.
        Raises:
            TransactionRuleError: If any requested ID is a split child.
            DatabaseError: On any database failure (entire batch rolled back).
        """
        if not transaction_ids:
            return {
                'deleted_count': 0, 'deleted_ids': [],
                'cascaded_ids': [], 'skipped_ids': []
            }
        unique_ids = list(dict.fromkeys(transaction_ids))
        try:
            deleted_ids: List[int] = []
            cascaded_ids: List[int] = []
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                # 1. Reject the whole batch if it contains any split children.
                split_children: List[int] = []
                for chunk in self._chunked(unique_ids, self._MAX_SQL_VARIABLES):
                    placeholders = ','.join('?' * len(chunk))
                    cursor.execute(
                        f"SELECT id FROM transactions "
                        f"WHERE id IN ({placeholders}) AND source_relationship = ?",
                        (*chunk, SOURCE_SPLIT)
                    )
                    split_children.extend(r['id'] for r in cursor.fetchall())
                if split_children:
                    raise TransactionRuleError(
                        f"Cannot bulk delete: {len(split_children)} of the selected "
                        f"transactions are lines of a split ({split_children}). "
                        f"Unsplit their source transactions first."
                    )
                # 2. Identify live rows so the response says which IDs moved.
                for chunk in self._chunked(unique_ids, self._MAX_SQL_VARIABLES):
                    placeholders = ','.join('?' * len(chunk))
                    cursor.execute(
                        f"SELECT id FROM transactions "
                        f"WHERE id IN ({placeholders}) AND deleted_at IS NULL",
                        chunk
                    )
                    deleted_ids.extend(r['id'] for r in cursor.fetchall())
                # 3. Explicit deletions, reason 'user'.
                for chunk in self._chunked(deleted_ids, self._MAX_SQL_VARIABLES):
                    placeholders = ','.join('?' * len(chunk))
                    cursor.execute(
                        f"UPDATE transactions "
                        f"SET deleted_at = {_NOW}, deleted_reason = ? "
                        f"WHERE id IN ({placeholders})",
                        (DELETED_REASON_USER, *chunk)
                    )
                # 4. Cascade. Runs after step 3, so explicitly-selected children
                #    are already deleted and the `deleted_at IS NULL` guard
                #    leaves their reason as 'user'.
                for chunk in self._chunked(deleted_ids, self._MAX_SQL_VARIABLES):
                    placeholders = ','.join('?' * len(chunk))
                    cursor.execute(
                        f"SELECT id FROM transactions "
                        f"WHERE source_transaction_id IN ({placeholders}) "
                        f"  AND source_relationship = ? "
                        f"  AND deleted_at IS NULL",
                        (*chunk, SOURCE_GENERATED)
                    )
                    children = [r['id'] for r in cursor.fetchall()]
                    if not children:
                        continue
                    child_placeholders = ','.join('?' * len(children))
                    cursor.execute(
                        f"UPDATE transactions "
                        f"SET deleted_at = {_NOW}, deleted_reason = ? "
                        f"WHERE id IN ({child_placeholders})",
                        (DELETED_REASON_CASCADE, *children)
                    )
                    cascaded_ids.extend(children)
            deleted_set = set(deleted_ids)
            skipped_ids = [i for i in unique_ids if i not in deleted_set]
            logger.info(
                f"Bulk soft-deleted {len(deleted_ids)} transactions "
                f"(requested {len(unique_ids)}, skipped {len(skipped_ids)}, "
                f"cascaded {len(cascaded_ids)})"
            )
            return {
                'deleted_count': len(deleted_ids),
                'deleted_ids': deleted_ids,
                'cascaded_ids': cascaded_ids,
                'skipped_ids': skipped_ids
            }
        except TransactionRuleError:
            raise
        except Exception as e:
            logger.error(f"Failed to bulk delete transactions: {e}")
            raise DatabaseError(f"Failed to bulk delete transactions: {e}") from e
        
    def restore_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """Restore a user-deleted transaction and its cascaded children.
        Enforces the three-line rule set:
            - `deleted_reason = 'user'`       → restorable here.
            - `deleted_reason = 'cascade'`    → restore the source instead.
            - `deleted_reason = 'superseded'` → unsplit instead.
            - `deleted_reason = 'unsplit'`    → re-split instead.
        Also enforces *child live implies parent live*: a generated child
        cannot be restored while its source transaction is deleted.
        Restores only children with `deleted_reason = 'cascade'`, so a
        child the user deleted by hand before deleting the parent stays
        deleted — which is what they asked for.
        Args:
            transaction_id: Primary key of the transaction to restore.
        Returns:
            Dict with:
                - `restored`: True if a deleted transaction was restored.
                  False if it doesn't exist or was never deleted.
                - `transaction_id`: Echoed back.
                - `restored_ids`: IDs of cascade-deleted children restored
                  alongside it.
        Raises:
            TransactionRuleError: If the row wasn't deleted by the user,
                or if restoring it would orphan it from a deleted parent.
            DatabaseError: On any database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                row = self._fetch_delete_state(cursor, transaction_id)
                if row is None or row['deleted_at'] is None:
                    logger.debug(
                        f"Transaction {transaction_id} not found or not deleted"
                    )
                    return {
                        'restored': False,
                        'transaction_id': transaction_id,
                        'restored_ids': []
                    }
                reason = row['deleted_reason']
                if reason not in RESTORABLE_REASONS:
                    help_text = _RESTORE_HELP.get(
                        reason, "it was not deleted by the user."
                    )
                    raise TransactionRuleError(
                        f"Cannot restore transaction {transaction_id}: {help_text}"
                    )
                # Invariant: a generated child may only be live if its source is.
                # Split children have the inverse invariant, but they can never
                # reach this point — delete_transaction() refuses them, so they
                # never carry reason='user'.
                if (row['source_relationship'] == SOURCE_GENERATED
                        and row['source_transaction_id'] is not None):
                    parent = self._fetch_delete_state(
                        cursor, row['source_transaction_id']
                    )
                    if parent is None or parent['deleted_at'] is not None:
                        raise TransactionRuleError(
                            f"Cannot restore transaction {transaction_id}: its source "
                            f"transaction {row['source_transaction_id']} is deleted. "
                            f"Restore the source transaction instead."
                        )
                cursor.execute('''
                    UPDATE transactions
                    SET deleted_at = NULL, deleted_reason = NULL
                    WHERE id = ? AND deleted_at IS NOT NULL
                ''', (transaction_id,))
                cursor.execute('''
                    SELECT id FROM transactions
                    WHERE source_transaction_id = ?
                      AND source_relationship = ?
                      AND deleted_reason = ?
                ''', (transaction_id, SOURCE_GENERATED, DELETED_REASON_CASCADE))
                restored_ids = [r['id'] for r in cursor.fetchall()]
                if restored_ids:
                    cursor.execute('''
                        UPDATE transactions
                        SET deleted_at = NULL, deleted_reason = NULL
                        WHERE source_transaction_id = ?
                          AND source_relationship = ?
                          AND deleted_reason = ?
                    ''', (transaction_id, SOURCE_GENERATED, DELETED_REASON_CASCADE))
            logger.info(
                f"Restored transaction {transaction_id}"
                + (f" (restored children {restored_ids})" if restored_ids else "")
            )
            return {
                'restored': True,
                'transaction_id': transaction_id,
                'restored_ids': restored_ids
            }
        except TransactionRuleError:
            raise
        except Exception as e:
            logger.error(f"Failed to restore transaction {transaction_id}: {e}")
            raise DatabaseError(f"Failed to restore transaction: {e}") from e

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
        """Find transactions matching given criteria with fuzzy tolerances.

        More flexible than `find_receipt_match_candidates()` — supports
        party-name matching and returns full hierarchy dicts. Used by
        the receipt-linking UI search.

        All search parameters are optional but at least one must be
        provided.

        Args:
            amount: Target amount. Matches within `amount_tolerance`.
            transaction_date: Target date (YYYY-MM-DD). Matches within
                `date_tolerance_days`.
            party_name: Substring match against both `parties.name` and
                `transactions.cleaned_description` (case-insensitive).
            amount_tolerance: Maximum absolute amount difference.
                Defaults to 0.01.
            date_tolerance_days: Maximum date difference in days.
                Defaults to 7.
            include_matched: If True, include transactions that already
                have a receipt. Defaults to True.
            limit: Maximum results to return. Defaults to 50.

        Returns:
            List of transaction dicts with hierarchy, ordered by date
            descending. Empty list if no matches.

        Raises:
            ValueError: If no search parameters are provided.
            DatabaseError: On query failure.
        """
        logger.debug(
            f"Finding matching transactions: amount={amount}, "
            f"date={transaction_date}, party={party_name}"
        )

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                conditions = []
                params = []

                if amount is not None:
                    conditions.append('ABS(t.amount - ?) <= ?')
                    params.extend([amount, amount_tolerance])

                if transaction_date:
                    conditions.append('ABS(julianday(t.transaction_date) - julianday(?)) <= ?')
                    params.extend([transaction_date, date_tolerance_days])

                if party_name:
                    conditions.append(
                        '(UPPER(p.name) LIKE UPPER(?) OR UPPER(t.cleaned_description) LIKE UPPER(?))'
                    )
                    params.extend([f'%{party_name}%', f'%{party_name}%'])

                if not include_matched:
                    conditions.append('t.receipt_id IS NULL')

                if not conditions:
                    raise ValueError("At least one search parameter is required")
                # Appended after the guard so it doesn't count as a
                # user-supplied search parameter.
                conditions.append('t.deleted_at IS NULL')

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

                logger.debug(f"Found {len(rows)} matching transactions")
                return [dict(row) for row in rows]

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to find matching transactions: {e}")
            raise DatabaseError(f"Failed to find matching transactions: {e}") from e

    def link_receipt_to_transaction(
        self,
        transaction_id: int,
        receipt_id: int
    ) -> Optional[Dict[str, Any]]:
        """Link a receipt to a transaction by setting `receipt_id`.

        Validates that the receipt exists before updating. A transaction
        can only be linked to one receipt at a time; calling this
        replaces any existing link.

        Args:
            transaction_id: Primary key of the transaction.
            receipt_id: Primary key of the receipt to link.

        Returns:
            The updated transaction dict with full hierarchy, or None
            if the transaction doesn't exist.

        Raises:
            not_found: (HTTP 404 via `api.utils.errors`) if the receipt
                does not exist.
            DatabaseError: On any other database failure.
        """
        logger.debug(f"Linking receipt {receipt_id} to transaction {transaction_id}")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT id FROM receipts WHERE id = ?', (receipt_id,))
                if not cursor.fetchone():
                    logger.warning(f"Receipt {receipt_id} not found for linking")
                    raise ValueError(f"Receipt {receipt_id} does not exist")

                cursor.execute(
                    'UPDATE transactions SET receipt_id = ? '
                    'WHERE id = ? AND deleted_at IS NULL',
                    (receipt_id, transaction_id)
                )

                if cursor.rowcount == 0:
                    logger.debug(f"Transaction {transaction_id} not found for receipt link")
                    return None

            logger.info(f"Linked receipt {receipt_id} to transaction {transaction_id}")
            return self.get_transaction_with_hierarchy(transaction_id)

        except ValueError:
            raise not_found(entity="Receipt", identifier=receipt_id)
        except Exception as e:
            logger.error(
                f"Failed to link receipt {receipt_id} to transaction {transaction_id}: {e}"
            )
            raise DatabaseError(f"Failed to link receipt to transaction: {e}") from e

    def _fetch_delete_state(self, cursor, transaction_id: int):
        """Read the columns needed to reason about deletion for one row.
        Deliberately ignores the soft-delete filter — callers need to see
        deleted rows to decide what to do with them.
        Args:
            cursor: An open cursor inside the caller's transaction.
            transaction_id: Primary key to look up.
        Returns:
            A `sqlite3.Row` with `id`, `deleted_at`, `deleted_reason`,
            `source_transaction_id` and `source_relationship`, or None.
        """
        cursor.execute('''
            SELECT id, deleted_at, deleted_reason,
                   source_transaction_id, source_relationship
            FROM transactions
            WHERE id = ?
        ''', (transaction_id,))
        return cursor.fetchone()
    def _live_generated_children(self, cursor, parent_id: int) -> List[int]:
        """Return IDs of live `generated` children of `parent_id`.
        Split children are excluded — they have inverted polarity and are
        never cascade-deleted. Rows the user already deleted by hand are
        excluded by the `deleted_at IS NULL` guard, so their
        `deleted_reason` is never overwritten with 'cascade'.
        Uses idx_transactions_source_transaction_id.
        """
        cursor.execute('''
            SELECT id FROM transactions
            WHERE source_transaction_id = ?
              AND source_relationship = ?
              AND deleted_at IS NULL
        ''', (parent_id, SOURCE_GENERATED))
        return [row['id'] for row in cursor.fetchall()]