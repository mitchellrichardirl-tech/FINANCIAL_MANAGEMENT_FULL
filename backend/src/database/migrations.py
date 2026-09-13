"""
Lightweight schema migrations for the SQLite database.
This module applies incremental schema changes that can't be expressed
in the base schema (e.g. adding columns to existing tables). Migrations
are idempotent — each one checks whether it has already been applied
before making changes, so `migrate()` is safe to call on every startup.
Called automatically by `connection.init_app()` when `create_tables=True`.

Three kinds of DDL, handled differently:
* MIGRATIONS - versioned, append-only. Never edit a shipped entry.
* INDEXES    - idempotent, reapplied on every startup. Edit in place.
* VIEWS      - idempotent, dropped and recreated on every startup. Edit in place.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from src.utils.logging import ContextLogger
logger = ContextLogger(__name__)

# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #

def _table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}

def _has_column(table: str, column: str) -> Callable[[sqlite3.Cursor], bool]:
    """Build a guard that reports whether `table.column` already exists."""
    def check(cursor: sqlite3.Cursor) -> bool:
        return column in _table_columns(cursor, table)
    return check

def _has_table(table: str) -> Callable[[sqlite3.Cursor], bool]:
    """Build a guard that reports whether `table` already exists."""
    def check(cursor: sqlite3.Cursor) -> bool:
        row = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None
    return check

@dataclass(frozen=True)
class Migration:
    name: str
    statements: tuple[str, ...]
    # Optional: lets an un-versioned legacy database recognise that this
    # migration has already been applied, so it can be skipped and stamped.
    is_applied: Callable[[sqlite3.Cursor], bool] | None = None


# --------------------------------------------------------------------------- #
# Versioned migrations - ORDER IS SIGNIFICANT, APPEND ONLY
# --------------------------------------------------------------------------- #
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        name="accounts.statement_format",
        is_applied=_has_column("accounts", "statement_format"),
        statements=(
            "ALTER TABLE accounts ADD COLUMN statement_format TEXT",
        ),
    ),
    Migration(
        name="transactions.source_transaction_id",
        is_applied=_has_column("transactions", "source_transaction_id"),
        statements=(
            "ALTER TABLE transactions ADD COLUMN source_transaction_id INTEGER "
            "REFERENCES transactions(id) ON DELETE SET NULL ON UPDATE CASCADE",
        ),
    ),
    Migration(
        # NULL default keeps this an O(1) metadata-only ALTER - SQLite does not
        # rewrite the table, so this is safe on a large transactions table.
        name="transactions.deleted_at",
        is_applied=_has_column("transactions", "deleted_at"),
        statements=(
            "ALTER TABLE transactions ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL",
        ),
    ),
    Migration(
        # Enables cascade deletion / restoration behaviour for generated
        # and split transactions.
        name="transactions.deleted_reason",
        is_applied=_has_column("transactions", "deleted_reason"),
        statements=(
            "ALTER TABLE transactions ADD COLUMN deleted_reason TEXT DEFAULT NULL",
        ),
    ),
    Migration(
        name="transactions.source_relationship",
        is_applied=_has_column("transactions", "source_relationship"),
        statements=(
            "ALTER TABLE transactions ADD COLUMN source_relationship TEXT DEFAULT NULL",
        ),
    ),
    Migration(
        # Persisted lifecycle state. Previously only existed as React state
        # in ProcessReceipts ('pending' | 'saved' | 'linked').
        # Non-NULL default is still metadata-only in SQLite - no table rewrite.
        name="receipts.status",
        is_applied=_has_column("receipts", "status"),
        statements=(
            "ALTER TABLE receipts ADD COLUMN status TEXT NOT NULL DEFAULT 'pending' "
            "CHECK (status IN ('pending', 'unlinked', 'linked'))",
        ),
    ),
    Migration(
        name="receipts.confirmed_at",
        is_applied=_has_column("receipts", "confirmed_at"),
        statements=(
            "ALTER TABLE receipts ADD COLUMN confirmed_at TIMESTAMP DEFAULT NULL",
        ),
    ),
    Migration(
        # Join table replaces transactions.receipt_id as the source of truth.
        # The column is retained as a denormalised mirror maintained by
        # ReceiptLinkService. UNIQUE constraints enforce today's 1:1 model;
        # relax (not drop) them when split receipts / split transactions land.
        name="receipt_links",
        is_applied=_has_table("receipt_links"),
        statements=(
            """
            CREATE TABLE receipt_links (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id      INTEGER NOT NULL
                                    REFERENCES receipts(id)
                                    ON DELETE CASCADE ON UPDATE CASCADE,
                transaction_id  INTEGER NOT NULL
                                    REFERENCES transactions(id)
                                    ON DELETE CASCADE ON UPDATE CASCADE,
                linked_at       TIMESTAMP NOT NULL
                                    DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                link_source     TEXT NOT NULL DEFAULT 'manual'
                                    CHECK (link_source IN ('manual', 'auto', 'import')),
                UNIQUE (receipt_id),
                UNIQUE (transaction_id)
            )
            """,
        ),
    ),
    Migration(
        # Populate receipt_links and receipts.status from the legacy
        # transactions.receipt_id column. Soft-deleted transactions keep
        # their receipts (restore must not lose the link). If a receipt is
        # referenced by more than one transaction, the live one wins;
        # INSERT OR IGNORE absorbs the remainder under UNIQUE(receipt_id).
        # No is_applied guard: receipt_links cannot pre-exist this code, so
        # an unversioned DB has never run this.
        name="receipts.backfill_status_and_links",
        statements=(
            """
            INSERT OR IGNORE INTO receipt_links (receipt_id, transaction_id, link_source)
            SELECT receipt_id, id, 'manual'
            FROM transactions
            WHERE receipt_id IS NOT NULL
            ORDER BY (deleted_at IS NULL) DESC, id ASC
            """,
            """
            UPDATE receipts
            SET status = 'linked',
                confirmed_at = COALESCE(confirmed_at, updated_at)
            WHERE id IN (SELECT receipt_id FROM receipt_links)
            """,
            """
            UPDATE receipts
            SET status = 'unlinked',
                confirmed_at = COALESCE(confirmed_at, updated_at)
            WHERE status = 'pending'
              AND vendor IS NOT NULL
            """,
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Idempotent indexes - reapplied every startup
# --------------------------------------------------------------------------- #
INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_transactions_source_transaction_id "
    "ON transactions(source_transaction_id)",
    # Partial index: covers the overwhelmingly common "live rows, ordered by
    # date" access path while excluding soft-deleted rows entirely.
    "CREATE INDEX IF NOT EXISTS idx_transactions_active_date "
    "ON transactions(transaction_date) "
    "WHERE deleted_at IS NULL",
    # Supports the anchor scan in pay_months: having resolved the set of
    # salary-typed parties, find their live transactions by date.
    "CREATE INDEX IF NOT EXISTS idx_transactions_active_party_date "
    "ON transactions(party_id, transaction_date) "
    "WHERE deleted_at IS NULL",
    # receipt_links(receipt_id) is covered by its UNIQUE constraint.
    "CREATE INDEX IF NOT EXISTS idx_receipt_links_transaction_id "
    "ON receipt_links(transaction_id)",
    "CREATE INDEX IF NOT EXISTS idx_receipts_status "
    "ON receipts(status)",
    # Partial index for the Unlinked view and candidate search: receipts
    # still awaiting a link, ordered by date.
    "CREATE INDEX IF NOT EXISTS idx_receipts_awaiting_link_date "
    "ON receipts(date) "
    "WHERE status != 'linked'",
)


# --------------------------------------------------------------------------- #
# Idempotent views - dropped and recreated every startup
# --------------------------------------------------------------------------- #
# Views that no longer exist. Dropped on startup, never recreated.
# Keep entries for a release or two after removal, then delete.
RETIRED_VIEWS: tuple[str, ...] = ()

VIEWS: dict[str, str] = {
    "pay_months": """
		WITH RECURSIVE
        -- 1. The range of months we care about
        bounds AS (
            SELECT date(MIN(transaction_date), 'start of month', '-1 month') AS first_month,
                date(MAX(transaction_date), 'start of month') AS last_month
            FROM transactions
            WHERE deleted_at IS NULL
        ),
        -- 2. A row per calendar month, including months with no transactions at all
        months(month_start) AS (
            SELECT first_month FROM bounds
            UNION ALL
            SELECT date(month_start, '+1 month')
            FROM months
            WHERE month_start < (SELECT last_month FROM bounds)
        ),
        -- 3. The largest Salary transaction in each month (ties -> earliest, then lowest id)
        ranked AS (
            SELECT date(t.transaction_date, 'start of month') AS month_start,
                t.transaction_date AS pay_date,
                ROW_NUMBER() OVER (
                    PARTITION BY date(t.transaction_date, 'start of month')
                    ORDER BY t.amount DESC, t.transaction_date ASC, t.id ASC
                ) AS rn
            FROM transactions AS t
            JOIN parties AS p ON t.party_id = p.id
            JOIN types AS ty ON p.type_id = ty.id
            WHERE 
               t.deleted_at IS NULL
            AND 
                ty.type = 'Salary'
        ),
        anchors AS (
            SELECT month_start, pay_date
            FROM ranked
            WHERE rn = 1
        ),
        -- 4. Every month, with its real pay date if it has one
        spine AS (
            SELECT m.month_start, a.pay_date
            FROM months m
            LEFT JOIN anchors a ON a.month_start = m.month_start
        ),
        -- 5. For each month, find the nearest preceding anchor; failing that, the nearest following one
        located AS (
            SELECT
                month_start,
                pay_date,
                MAX(CASE WHEN pay_date IS NOT NULL THEN month_start END)
                    OVER (ORDER BY month_start
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS prev_anchor,
                MIN(CASE WHEN pay_date IS NOT NULL THEN month_start END)
                    OVER (ORDER BY month_start
                        ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_anchor
            FROM spine
        ),
        -- 6. Resolve the anchor and how many months we need to shift it by
        resolved AS (
            SELECT
                month_start,
                pay_date,
                COALESCE(prev_anchor, next_anchor) AS anchor_month,
                (CAST(strftime('%Y', month_start) AS INTEGER) * 12
            + CAST(strftime('%m', month_start) AS INTEGER))
            - (CAST(strftime('%Y', COALESCE(prev_anchor, next_anchor)) AS INTEGER) * 12
            + CAST(strftime('%m', COALESCE(prev_anchor, next_anchor)) AS INTEGER)) AS n_months
            FROM located
        ),
        pay_dates AS (
			SELECT
				r.month_start,
				COALESCE(
					date(a.pay_date, 'start of month', printf('%+d months', r.n_months),
						printf('+%d days',
								MIN(CAST(strftime('%d', a.pay_date) AS INTEGER),
									CAST(strftime('%d', date(a.pay_date, 'start of month',
															printf('%+d months', r.n_months),
															'+1 month', '-1 day')) AS INTEGER)
								) - 1)
					),
					r.month_start                 -- fallback: 1st of the month
				) AS pay_start_date,
				CASE
					WHEN r.pay_date IS NOT NULL THEN 'actual'
					WHEN r.n_months > 0         THEN 'carried forward'
					ELSE                             'carried backward'
				END AS source
			FROM resolved r
			JOIN anchors a ON a.month_start = r.anchor_month
			ORDER BY r.month_start
		)
		SELECT
			month_start,
			pay_start_date,
			date(
				LEAD (pay_start_date,
					1,
					date(pay_start_date, '+1 month')
				) OVER (ORDER BY month_start ),
				'-1 day'
			) AS pay_end_date
		FROM
			pay_dates;
    """,
    "export": """
        SELECT
            t.id
            , t.transaction_date
            , t.amount
            , t.description
            , t.cleaned_description
            , t.is_credit
            , t.is_kids
            , t.is_one_off
            , a.account_name
            , p.name AS party
            , ty.type
            , sc.sub_category
            , c.category
            , r.original_filename AS receipt
            , pm.month_start AS pay_month
        FROM transactions t
        LEFT JOIN accounts a
            ON t.account_id = a.id
        LEFT JOIN parties p
            ON t.party_id = p.id
        LEFT JOIN types ty
            ON p.type_id = ty.id
        LEFT JOIN sub_categories sc
            ON ty.sub_category_id = sc.id
        LEFT JOIN categories c
            ON sc.category_id = c.id
        LEFT JOIN receipts r
            ON t.receipt_id = r.id
        LEFT JOIN pay_months pm
            ON (t.transaction_date >= pm.pay_start_date) AND (t.transaction_date <= pm.pay_end_date)
        WHERE t.deleted_at IS NULL
        ORDER BY
            t.transaction_date ASC,
            t.amount DESC;
    """
}


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def migrate(db_path: str) -> None:
    """Apply all pending schema migrations to the database.
    Args:
        db_path: Filesystem path to the SQLite database file.
    Note:
        Opens its own connection rather than using `ConnectionManager`
        to avoid a circular import with `connection.py`.
        Must run *after* the base schema exists - the migrations assume
        `accounts` and `transactions` are already present.
    """
    # isolation_level=None -> autocommit; we drive transactions explicitly.
    # The sqlite3 module only opens implicit transactions before DML, not DDL,
    # so `with conn:` would not actually wrap these ALTER statements.
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        cursor = conn.cursor()
        _drop_views(cursor)       # before ALTERs: a view can block a rename
        _apply_migrations(cursor)
        _apply_indexes(cursor)
        _create_views(cursor)
    finally:
        conn.close()

def _apply_migrations(cursor: sqlite3.Cursor) -> None:
    version = cursor.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRATIONS):
        raise RuntimeError(
            f"Database schema version {version} is newer than this code "
            f"understands ({len(MIGRATIONS)}). Refusing to continue."
        )
    for index, migration in enumerate(MIGRATIONS):
        target = index + 1
        if target <= version:
            continue
        # Legacy databases carry user_version == 0 but may already have the
        # columns. Detect that, stamp, and move on rather than re-ALTERing.
        if migration.is_applied is not None and migration.is_applied(cursor):
            _stamp(cursor, target)
            logger.info("Migration already applied: %s", migration.name)
            continue
        cursor.execute("BEGIN")
        try:
            for statement in migration.statements:
                cursor.execute(statement)
            _stamp(cursor, target)
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            logger.exception("Migration failed: %s", migration.name)
            raise
        logger.info("Migration complete: %s", migration.name)

def _stamp(cursor: sqlite3.Cursor, version: int) -> None:
    # PRAGMA values cannot be parameterised; int() keeps this injection-safe.
    cursor.execute(f"PRAGMA user_version = {int(version)}")

def _apply_indexes(cursor: sqlite3.Cursor) -> None:
    for statement in INDEXES:
        cursor.execute(statement)

def _drop_views(cursor: sqlite3.Cursor) -> None:
    for name in (*VIEWS, *RETIRED_VIEWS):
        cursor.execute(f"DROP VIEW IF EXISTS {name}")

def _create_views(cursor: sqlite3.Cursor) -> None:
    for name, body in VIEWS.items():
        cursor.execute(f"CREATE VIEW {name} AS {body.strip().rstrip(';')}")
        exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = ?",
            (name,),
        ).fetchone()
        if exists is None:
            raise RuntimeError(f"View {name!r} was not created")
        # CREATE VIEW resolves nothing - a body naming a missing column still
        # creates cleanly and only fails when something selects from it.
        try:
            cursor.execute(f"SELECT * FROM {name} LIMIT 1").fetchall()
        except sqlite3.Error as exc:
            raise RuntimeError(f"View {name!r} is not queryable: {exc}") from exc
        logger.info("View created: %s", name)
