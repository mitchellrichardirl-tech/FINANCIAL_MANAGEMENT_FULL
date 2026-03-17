"""
Base repository with shared SQL execution helpers.

Currently thin — just `insert_query` and `select_query` wrappers that add
logging and translate sqlite3 exceptions into `DatabaseError`. Individual
repositories (`accounts.py`, `transactions.py`, etc.) mostly write their
own SQL rather than building on this; consolidating that is on the backlog.
"""

from typing import Optional, Tuple, Any

from src.database.connection import get_manager, DatabaseError
from src.utils.logging import ContextLogger
import sqlite3

logger = ContextLogger(__name__)


class BaseRepository:
    """
    Shared DB access helpers for repository subclasses.

    Provides connection acquisition (via the global manager) and two
    execution wrappers that handle logging and exception translation.
    Subclasses are expected to compose their own queries and call
    `insert_query` / `select_query` rather than touching `self.db` directly —
    though in practice many still do. Tightening that contract is future work.
    """

    def __init__(self):
        self.db = get_manager()

    def insert_query(self, query: str, values: Tuple) -> int:
        """
        Execute an INSERT inside a transaction and return the new row id.

        Runs inside `self.db.transaction()`, which commits on success and
        rolls back on exception — no manual commit needed.

        Args:
            query: Parameterized INSERT statement.
            values: Values to bind. Must match the placeholders in `query`.

        Returns:
            `lastrowid` of the inserted row.

        Raises:
            DatabaseError: On any failure. UNIQUE constraint violations get
                a "Record already exists" message; everything else is wrapped
                generically.
        """
        logger.debug(f"Executing insert: {query[:50]}...")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, values)
                row_id = cursor.lastrowid

            logger.debug(f"Insert successful, id={row_id}")
            return row_id

        except sqlite3.IntegrityError as e:
            error_str = str(e).lower()
            if "unique" in error_str:
                logger.warning(f"Duplicate record: {e}")
                raise DatabaseError(f"Record already exists: {values}") from e
            logger.error(f"Integrity error on insert: {e}")
            raise DatabaseError(f"Failed to add record: {e}") from e
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            raise DatabaseError(f"Failed to add record: {e}") from e

    # TODO: Maybe split into `fetch_one` and `fetch_all` for clarity
    def select_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        all_rows: bool = False
    ) -> Any:
        """
        Execute a SELECT and return the result.

        Args:
            query: Parameterized SELECT statement.
            params: Values to bind, or None for a parameterless query.
            all_rows: If True, `fetchall()`; if False, `fetchone()`.

        Returns:
            - `all_rows=True` → list of `sqlite3.Row` (possibly empty)
            - `all_rows=False` → single `sqlite3.Row`, or `None` if no match

        Raises:
            DatabaseError: On any query failure.
        """
        logger.debug(f"Executing select: {query[:50]}... | all_rows={all_rows}")

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                if all_rows:
                    rows = cursor.fetchall()
                    logger.debug(f"Select returned {len(rows)} rows")
                    return rows

                row = cursor.fetchone()
                logger.debug(f"Select returned {'1 row' if row else 'no rows'}")
                return row

        except Exception as e:
            logger.error(f"Select failed: {e}")
            raise DatabaseError(f"Failed to query records: {e}") from e