"""
Repository for account database operations.

Provides CRUD access to the `accounts` table through the
`AccountRepository` class. Accounts represent bank or card accounts
that transactions are imported from.

Each account has a name, type (e.g. "current", "credit"), and an
optional `statement_format` that links to the statement parser registry
for automatic file parsing.

Typical usage:
    repo = AccountRepository()
    account = repo.add_account("Main Current", "current", statement_format="aib")
    all_accounts = repo.get_all_accounts()
"""

from typing import Optional, Dict, List, Any
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.base import BaseRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class AccountRepository:
    """Repository for account CRUD operations.

    Wraps all database access for the `accounts` table behind a clean
    method interface. Uses `ConnectionManager.transaction()` for writes
    and `ConnectionManager.get_connection()` for reads.

    All methods raise `DatabaseError` on failure, with specific messages
    for constraint violations (e.g. duplicate account names).

    Attributes:
        db: The `ConnectionManager` used for database access.
        br: A `BaseRepository` instance providing shared query helpers.
    """

    def __init__(self):
        """Initialize the repository.

        Retrieves the module-level `ConnectionManager` via `get_manager()`.
        Must be called after `connection.init()` or `connection.init_app()`.
        """
        self.db = get_manager()
        self.br = BaseRepository()

    # ========== Create ==========

    def add_account(
        self,
        account_name: str,
        account_type: str,
        statement_format: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new account and return the full record.

        Args:
            account_name: Display name for the account (must be unique).
            account_type: Account kind (e.g. "current", "credit", "savings").
            statement_format: Optional identifier for the statement parser
                to use when importing files for this account (e.g. "aib",
                "revolut"). Can be set later via `update_account()`.

        Returns:
            Dict of the newly created account row, or None if the row
            could not be retrieved after insert.

        Raises:
            DatabaseError: If the account name already exists or the
                insert fails for any other reason.
        """
        logger.debug(f"Adding account: {account_name} ({account_type})")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """INSERT INTO accounts
                       (account_name, account_type, statement_format)
                       VALUES (?, ?, ?)""",
                    (account_name, account_type, statement_format),
                )
                account_id = cursor.lastrowid

                cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
                row = cursor.fetchone()

            logger.info(f"Added account {account_id}: {account_name}")
            return dict(row) if row else None

        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                logger.warning(f"Duplicate account name: {account_name}")
                raise DatabaseError(f"Account already exists: {account_name}") from e
            logger.error(f"Integrity error adding account: {e}")
            raise DatabaseError(f"Failed to add account: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add account: {e}")
            raise DatabaseError(f"Failed to add account: {e}") from e

    # ========== Read ==========

    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single account by its primary key.

        Args:
            account_id: The account's `id` value.

        Returns:
            Dict of the account row, or None if no account exists with
            the given ID.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            row = self.br.select_query(
                "SELECT * FROM accounts WHERE id = ?",
                params=(account_id,),
            )
            if not row:
                logger.debug(f"Account {account_id} not found")
                return None
            return dict(row)

        except Exception as e:
            logger.error(f"Failed to get account {account_id}: {e}")
            raise DatabaseError(f"Failed to get account: {e}") from e

    def get_account_by_name(self, account_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single account by its name.

        Args:
            account_name: The exact account name to match.

        Returns:
            Dict of the account row, or None if no match is found.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM accounts WHERE account_name = ?",
                    (account_name,),
                )
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Account not found by name: {account_name}")
                    return None
                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get account by name '{account_name}': {e}")
            raise DatabaseError(f"Failed to get account: {e}") from e

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Retrieve all accounts, ordered alphabetically by name.

        Returns:
            List of account dicts. Empty list if no accounts exist.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM accounts ORDER BY account_name")
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} accounts")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all accounts: {e}")
            raise DatabaseError(f"Failed to get accounts: {e}") from e

    def get_accounts_by_type(self, account_type: str) -> List[Dict[str, Any]]:
        """Retrieve all accounts of a given type.

        Args:
            account_type: The type to filter by (e.g. "current", "credit").

        Returns:
            List of matching account dicts, ordered by name. Empty list
            if no accounts match.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM accounts WHERE account_type = ? ORDER BY account_name",
                    (account_type,),
                )
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} accounts of type '{account_type}'")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get accounts by type '{account_type}': {e}")
            raise DatabaseError(f"Failed to get accounts: {e}") from e

    def get_accounts_by_statement_format(
        self, statement_format: str
    ) -> List[Dict[str, Any]]:
        """Retrieve all accounts that use a specific statement format.

        Args:
            statement_format: The parser identifier to filter by
                (e.g. "aib", "revolut", "ptsb").

        Returns:
            List of matching account dicts, ordered by name. Empty list
            if no accounts match.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM accounts
                       WHERE statement_format = ?
                       ORDER BY account_name""",
                    (statement_format,),
                )
                rows = cursor.fetchall()

                logger.debug(
                    f"Retrieved {len(rows)} accounts with "
                    f"statement format '{statement_format}'"
                )
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(
                f"Failed to get accounts by statement format "
                f"'{statement_format}': {e}"
            )
            raise DatabaseError(f"Failed to get accounts: {e}") from e

    def get_accounts_without_statement_format(self) -> List[Dict[str, Any]]:
        """Retrieve accounts that have no statement format configured.

        Useful for identifying accounts that need manual parser
        assignment before statement import will work.

        Returns:
            List of account dicts where `statement_format` is NULL,
            ordered by name.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM accounts
                       WHERE statement_format IS NULL
                       ORDER BY account_name"""
                )
                rows = cursor.fetchall()

                logger.debug(
                    f"Retrieved {len(rows)} accounts without statement format"
                )
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get unconfigured accounts: {e}")
            raise DatabaseError(f"Failed to get accounts: {e}") from e

    # ========== Update ==========

    def update_account(
        self,
        account_id: int,
        account_name: Optional[str] = None,
        account_type: Optional[str] = None,
        statement_format: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an account's fields selectively.

        Only the fields passed with non-None values are modified. If no
        fields are provided the existing record is returned unchanged.

        Args:
            account_id: The ID of the account to update.
            account_name: New display name (must remain unique).
            account_type: New account type.
            statement_format: New statement parser identifier.

        Returns:
            Dict of the updated account row, or None if no account
            exists with the given ID.

        Raises:
            DatabaseError: If the new name conflicts with an existing
                account or the update fails for any other reason.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if account_name is not None:
                    updates.append("account_name = ?")
                    params.append(account_name)
                    updated_fields.append("account_name")

                if account_type is not None:
                    updates.append("account_type = ?")
                    params.append(account_type)
                    updated_fields.append("account_type")

                if statement_format is not None:
                    updates.append("statement_format = ?")
                    params.append(statement_format)
                    updated_fields.append("statement_format")

                if not updates:
                    logger.debug(f"No fields to update for account {account_id}")
                    return self.get_account_by_id(account_id)

                params.append(account_id)
                query = f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Account {account_id} not found for update")
                    return None

            logger.info(f"Updated account {account_id}: {updated_fields}")
            return self.get_account_by_id(account_id)

        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                logger.warning(f"Duplicate account name on update: {account_name}")
                raise DatabaseError(
                    f"Account name already exists: {account_name}"
                ) from e
            logger.error(f"Integrity error updating account {account_id}: {e}")
            raise DatabaseError(f"Failed to update account: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update account {account_id}: {e}")
            raise DatabaseError(f"Failed to update account: {e}") from e

    # ========== Delete ==========

    def delete_account(self, account_id: int) -> bool:
        """Delete an account by ID.

        Checks for associated transactions before deleting. If the
        account has any linked transactions the delete is refused to
        prevent orphaned records.

        Args:
            account_id: The ID of the account to delete.

        Returns:
            True if the account was deleted, False if no account exists
            with the given ID.

        Raises:
            DatabaseError: If the account has associated transactions or
                the delete fails for any other reason.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE account_id = ? AND deleted_at IS NULL",
                    (account_id,),
                )
                count = cursor.fetchone()["count"]

                if count > 0:
                    logger.warning(
                        f"Cannot delete account {account_id}: "
                        f"has {count} associated transactions"
                    )
                    raise DatabaseError(
                        f"Cannot delete account {account_id}: "
                        f"has {count} associated transaction(s)"
                    )

                cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

                if cursor.rowcount == 0:
                    logger.debug(f"Account {account_id} not found for deletion")
                    return False

                logger.info(f"Deleted account {account_id}")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete account {account_id}: {e}")
            raise DatabaseError(f"Failed to delete account: {e}") from e

    # ========== Utility ==========

    def get_account_transaction_count(self, account_id: int) -> int:
        """Count the transactions linked to an account.

        Useful for UI display and for pre-delete validation.

        Args:
            account_id: The account to count transactions for.

        Returns:
            Number of transactions. Returns 0 if the account has no
            transactions or does not exist.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE account_id = ? AND deleted_at IS NULL",
                    (account_id,),
                )
                row = cursor.fetchone()
                count = row["count"] if row else 0

                logger.debug(f"Account {account_id} has {count} transactions")
                return count

        except Exception as e:
            logger.error(
                f"Failed to get transaction count for account {account_id}: {e}"
            )
            raise DatabaseError(f"Failed to get transaction count: {e}") from e

    def get_distinct_account_types(self) -> List[str]:
        """Retrieve all distinct account type values.

        Useful for populating filter dropdowns in the UI.

        Returns:
            Sorted list of unique account type strings. Empty list if
            no accounts exist.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT account_type FROM accounts ORDER BY account_type"
                )
                rows = cursor.fetchall()
                types = [row["account_type"] for row in rows]

                logger.debug(f"Retrieved {len(types)} distinct account types")
                return types

        except Exception as e:
            logger.error(f"Failed to get distinct account types: {e}")
            raise DatabaseError(f"Failed to get account types: {e}") from e
        

    # ========== Cash Account ==========

    CASH_ACCOUNT_NAME = "Cash"
    CASH_ACCOUNT_TYPE = "cash"

    def ensure_cash_account(self) -> Dict[str, Any]:
        """Get the Cash account, creating it if it does not exist.

        Uses the well-known name ``"Cash"`` with type ``"cash"``.
        Safe to call repeatedly — the first call creates the account
        and subsequent calls return the existing record.

        Returns:
            Dict of the Cash account row.

        Raises:
            DatabaseError: If creation or lookup fails.
        """
        account = self.get_account_by_name(self.CASH_ACCOUNT_NAME)
        if account:
            logger.debug(f"Cash account exists: id={account['id']}")
            return account

        logger.info("Creating Cash account")
        return self.add_account(self.CASH_ACCOUNT_NAME, self.CASH_ACCOUNT_TYPE)