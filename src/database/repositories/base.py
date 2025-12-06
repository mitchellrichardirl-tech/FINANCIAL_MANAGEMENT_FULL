from typing import Optional, Dict, List, Any, Tuple
import logging
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.models.transaction import Transaction

logger = logging.getLogger(__name__)

class BaseRepository:
    
    def __init__(self):
        self.db = get_manager()

    def insert_query(self, query: str, values: Tuple):
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, values)
                conn.commit()
                id = cursor.lastrowid
                return id
        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                raise DatabaseError(f"Record already exists: {values}") from e
            raise DatabaseError(f"Failed to add record: {e}") from e
        except Exception as e:
            raise DatabaseError(f"Failed to add record: {e}") from e
        
    def select_query(self, query: str,
                     params: Optional[str] = None,
                     all_rows: Optional[bool] = False
                     ):
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                if all_rows:
                    return cursor.fetchall()
                return cursor.fetchone()
        except Exception as e:
            raise DatabaseError(f"Failed to query records: {e}") from e