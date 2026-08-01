"""
Lightweight schema migrations for the SQLite database.
This module applies incremental schema changes that can't be expressed
in the base schema (e.g. adding columns to existing tables). Migrations
are idempotent — each one checks whether it has already been applied
before making changes, so `migrate()` is safe to call on every startup.
Called automatically by `connection.init_app()` when `create_tables=True`.
"""
import sqlite3
from src.utils.logging import ContextLogger
logger = ContextLogger(__name__)

def _table_columns(cursor: sqlite3.Cursor, table: str) -> list[str]:
    """Return the current column names for `table`.
    Re-queried per migration rather than cached, so that a migration can
    safely inspect the schema left behind by the one before it.
    Args:
        cursor: An open cursor on the target database.
        table: Name of the table to inspect.
    Returns:
        List of column names in declaration order.
    """
    return [row[1] for row in cursor.execute(f"PRAGMA table_info({table})")]

def migrate(db_path: str):
    """Apply all pending schema migrations to the database.
    Currently applies the following migrations:
        1. Add `statement_format` TEXT column to the `accounts` table.
        2. Add `source_transaction_id` INTEGER column to the
           `transactions` table, with a self-referencing FK and index.
        3. Add `deleted_at` TIMESTAMP column to the `transactions` table
           for soft deletes, with a partial index covering live rows.
    Each migration inspects the current schema and only runs if its
    change is not already present, so repeated calls are safe.
    Args:
        db_path: Filesystem path to the SQLite database file.
    Note:
        Opens its own connection rather than using `ConnectionManager`
        to avoid a circular import with `connection.py`.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # --- Migration 1: accounts.statement_format ---
    if "statement_format" not in _table_columns(cursor, "accounts"):
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN statement_format TEXT"
        )
        conn.commit()
        logger.info("Migration complete: added 'statement_format' column")
    else:
        logger.info("Migration already applied: accounts.statement_format")
    # --- Migration 2: transactions.source_transaction_id ---
    if "source_transaction_id" not in _table_columns(cursor, "transactions"):
        cursor.execute(
            "ALTER TABLE transactions ADD COLUMN source_transaction_id INTEGER "
            "REFERENCES transactions(id) ON DELETE SET NULL ON UPDATE CASCADE"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_source_transaction_id "
            "ON transactions(source_transaction_id)"
        )
        conn.commit()
        logger.info(
            "Migration complete: added 'source_transaction_id' column "
            "and index to transactions"
        )
    else:
        logger.info(
            "Migration already applied: transactions.source_transaction_id"
        )
    # --- Migration 3: transactions.deleted_at (soft delete) ---
    if "deleted_at" not in _table_columns(cursor, "transactions"):
        # NULL default keeps this an O(1) metadata-only ALTER — SQLite does
        # not rewrite the table, so this is safe on a large transactions table.
        cursor.execute(
            "ALTER TABLE transactions ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL"
        )
        # Partial index: covers the overwhelmingly common "live rows, ordered
        # by date" access path while excluding soft-deleted rows entirely.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_active_date "
            "ON transactions(transaction_date) "
            "WHERE deleted_at IS NULL"
        )
        conn.commit()
        logger.info(
            "Migration complete: added 'deleted_at' column "
            "and partial index to transactions"
        )
    else:
        logger.info("Migration already applied: transactions.deleted_at")
    conn.close()