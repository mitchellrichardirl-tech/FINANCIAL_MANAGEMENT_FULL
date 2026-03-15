from typing import Optional, Tuple, Any

from src.database.connection import get_manager, DatabaseError
from src.utils.logging import ContextLogger
import sqlite3

logger = ContextLogger(__name__)


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self):
        self.db = get_manager()

    def insert_query(self, query: str, values: Tuple) -> int:
        """
        Execute an INSERT query and return the last row ID.
        
        Note: Uses transaction() which auto-commits, so the explicit
        conn.commit() is redundant and has been removed.
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

    def select_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        all_rows: bool = False
    ) -> Any:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters (should be a tuple)
            all_rows: If True, return all rows; otherwise return first row
            
        Returns:
            Single row, list of rows, or None
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