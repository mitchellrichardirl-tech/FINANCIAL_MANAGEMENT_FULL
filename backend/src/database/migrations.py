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


def migrate(db_path: str):
    """Apply all pending schema migrations to the database.

    Currently applies the following migrations:
        1. Add `statement_format` TEXT column to the `accounts` table.
        2. Add `source_transaction_id` INTEGER column to the
           `transactions` table, with a self-referencing FK and index.

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
    account_columns = [
        row[1] for row in cursor.execute("PRAGMA table_info(accounts)")
    ]

    if "statement_format" not in account_columns:
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN statement_format TEXT"
        )
        conn.commit()
        logger.info("Migration complete: added 'statement_format' column")
    else:
        logger.info("Migration already applied: accounts.statement_format")

    # --- Migration 2: transactions.source_transaction_id ---
    transaction_columns = [
        row[1] for row in cursor.execute("PRAGMA table_info(transactions)")
    ]

    if "source_transaction_id" not in transaction_columns:
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

    conn.close()