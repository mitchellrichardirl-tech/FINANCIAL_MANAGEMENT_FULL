from typing import Optional, Dict, List, Any, Union
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.base import BaseRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class AccountRepository:
    """Repository for account CRUD operations."""

    def __init__(self):
        self.db = get_manager()
        self.br = BaseRepository()

   # ========== Create ==========

    def add_account(
        self,
        account_name: str,
        account_type: str
    ) -> Optional[Dict[str, Any]]:
        """Add a new account and return the created record."""
        logger.debug(f"Adding account: {account_name} ({account_type})")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "INSERT INTO accounts (account_name, account_type) VALUES (?, ?)",
                    (account_name, account_type)
                )
                account_id = cursor.lastrowid
                
                # Fetch within same transaction
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
        """Get an account by ID."""
        try:
            row = self.br.select_query(
                "SELECT * FROM accounts WHERE id = ?",
                params=str(account_id)
            )
            if not row:
                logger.debug(f"Account {account_id} not found")
                return None
            return dict(row)

        except Exception as e:
            logger.error(f"Failed to get account {account_id}: {e}")
            raise DatabaseError(f"Failed to get account: {e}") from e

    def get_account_by_name(self, account_name: str) -> Optional[Dict[str, Any]]:
        """Get an account by name."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM accounts WHERE account_name = ?",
                    (account_name,)
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
        """Get all accounts."""
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
        """Get all accounts of a specific type."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM accounts WHERE account_type = ? ORDER BY account_name",
                    (account_type,)
                )
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} accounts of type '{account_type}'")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get accounts by type '{account_type}': {e}")
            raise DatabaseError(f"Failed to get accounts: {e}") from e

    # ========== Update ==========

    def update_account(
        self,
        account_id: int,
        account_name: Optional[str] = None,
        account_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an account."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if account_name is not None:
                    updates.append("account_name = ?")
                    params.append(account_name)
                    updated_fields.append('account_name')

                if account_type is not None:
                    updates.append("account_type = ?")
                    params.append(account_type)
                    updated_fields.append('account_type')

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
                raise DatabaseError(f"Account name already exists: {account_name}") from e
            logger.error(f"Integrity error updating account {account_id}: {e}")
            raise DatabaseError(f"Failed to update account: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update account {account_id}: {e}")
            raise DatabaseError(f"Failed to update account: {e}") from e

    # ========== Delete ==========

    def delete_account(self, account_id: int) -> bool:
        """
        Delete an account by ID.
        
        Returns True if deleted, False if not found.
        Raises DatabaseError if account has associated transactions.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE account_id = ?",
                    (account_id,)
                )
                count = cursor.fetchone()['count']

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
        """Get the number of transactions for an account."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE account_id = ?",
                    (account_id,)
                )
                row = cursor.fetchone()
                count = row['count'] if row else 0

                logger.debug(f"Account {account_id} has {count} transactions")
                return count

        except Exception as e:
            logger.error(f"Failed to get transaction count for account {account_id}: {e}")
            raise DatabaseError(f"Failed to get transaction count: {e}") from e

    def get_distinct_account_types(self) -> List[str]:
        """Get all distinct account types."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT account_type FROM accounts ORDER BY account_type"
                )
                rows = cursor.fetchall()
                types = [row['account_type'] for row in rows]

                logger.debug(f"Retrieved {len(types)} distinct account types")
                return types

        except Exception as e:
            logger.error(f"Failed to get distinct account types: {e}")
            raise DatabaseError(f"Failed to get account types: {e}") from e