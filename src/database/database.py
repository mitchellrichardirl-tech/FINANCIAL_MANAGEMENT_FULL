from typing import Union, Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
import logging
import sqlite3
import json

from src.models.receipt import Receipt

_UNSET = object()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass


class Database:
    def __init__(self, db_path: Union[Path, str] = "data.db"):
        self.db_path = Path(db_path)
        self._ensure_directory_exists()
        self.init_db()

    def _ensure_directory_exists(self):
        """Ensure the directory for the database exists"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")  # Better concurrency
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise DatabaseError(f"Database connection failed: {e}") from e
        
        try:
            yield conn
        finally:
            if conn:
                conn.close()

    def init_db(self):
        """Initialize database with all required tables"""
        logger.info("Initializing database...")
        try:
            self.create_receipts_table()
            # self.create_financial_tables()  # Uncomment when implemented
            logger.info("✓ Database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_receipts_table(self):
        """Create receipts table with proper schema"""
        logger.info("Creating receipts table if not exists...")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    vendor TEXT,
                    date DATE,
                    amount REAL CHECK(amount >= 0),
                    confidence INTEGER DEFAULT 0 CHECK(confidence >= 0 AND confidence <= 3),
                    selected_method TEXT,
                    raw_text TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                    updated_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                    UNIQUE (stored_filename)
                )
            ''')
            
            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_receipts_vendor 
                ON receipts(vendor)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_receipts_date 
                ON receipts(date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_receipts_created 
                ON receipts(created_at)
            ''')
            
            # Create trigger to update updated_at with subsecond precision
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS update_receipts_timestamp 
                AFTER UPDATE ON receipts
                BEGIN
                    UPDATE receipts SET updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    WHERE id = NEW.id;
                END
            ''')
            
            conn.commit()
            logger.info("✓ Receipts table ready")

    def save_receipt(self, receipt: Receipt) -> int:
        """Save receipt to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Prepare metadata
                metadata = {
                    'selected_method': getattr(receipt, 'selected_method', None),
                    'processing_time': getattr(receipt, 'processing_time', None),
                }
                
                # Convert date to proper format
                date_str = None
                if receipt.date:
                    if isinstance(receipt.date, datetime):
                        date_str = receipt.date.date().isoformat()
                    else:
                        date_str = str(receipt.date)
                
                cursor.execute('''
                    INSERT INTO receipts (
                        original_filename, stored_filename, file_path,
                        vendor, amount, date, confidence, selected_method,
                        raw_text, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    receipt.original_filename,
                    receipt.stored_filename,
                    str(receipt.file_path),
                    receipt.vendor,
                    receipt.amount,
                    date_str,
                    receipt.confidence,
                    getattr(receipt, 'selected_method', None),
                    getattr(receipt, 'extracted_text', None),
                    json.dumps(metadata)
                ))
                
                receipt_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"Saved receipt {receipt_id}: {receipt.original_filename}")
                return receipt_id
                
        except sqlite3.IntegrityError as e:
            logger.error(f"Receipt already exists: {e}")
            raise DatabaseError(f"Receipt already exists: {receipt.stored_filename}") from e
        except Exception as e:
            logger.error(f"Failed to save receipt: {e}")
            raise DatabaseError(f"Failed to save receipt: {e}") from e

    def get_receipts(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        vendor: Optional[str] = None,
        min_confidence: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get receipts with optional filters"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                conditions = []
                params = []
                
                if vendor:
                    conditions.append('vendor LIKE ?')
                    params.append(f'%{vendor}%')
                
                if min_confidence is not None:
                    conditions.append('confidence >= ?')
                    params.append(min_confidence)
                
                if start_date:
                    conditions.append('date >= ?')
                    params.append(start_date.date().isoformat())
                
                if end_date:
                    conditions.append('date <= ?')
                    params.append(end_date.date().isoformat())
                
                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                
                query = f'''
                    SELECT * FROM receipts 
                    {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                '''
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                receipts = [self._row_to_dict(row) for row in cursor.fetchall()]
                
                return receipts
                
        except Exception as e:
            logger.error(f"Failed to get receipts: {e}")
            raise DatabaseError(f"Failed to get receipts: {e}") from e

    def get_receipt_by_id(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific receipt"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,))
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to get receipt: {e}") from e

    def update_receipt(
        self,
        receipt_id: int,
        vendor: Optional[str] = _UNSET, # type: ignore
        amount: Optional[float] = _UNSET, # type: ignore
        date: Optional[datetime] = _UNSET, # type: ignore
        confidence: Optional[int] = _UNSET, # type: ignore
        raw_text: Optional[str] = _UNSET # type: ignore
        ) -> Optional[Dict[str, Any]]:
        """Update receipt data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if vendor is not _UNSET:
                    updates.append('vendor = ?')
                    params.append(vendor)
                
                if amount is not _UNSET:
                    updates.append('amount = ?')
                    params.append(amount)
                
                if date is not _UNSET:
                    updates.append('date = ?')
                    date_str = date.date().isoformat() if isinstance(date, datetime) else str(date)
                    params.append(date_str)
                
                if confidence is not _UNSET:
                    updates.append('confidence = ?')
                    params.append(confidence)
                
                if raw_text is not _UNSET:
                    updates.append('raw_text = ?')
                    params.append(raw_text)
                
                if not updates:
                    return self.get_receipt_by_id(receipt_id)
                
                params.append(receipt_id)
                
                query = f"UPDATE receipts SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Receipt {receipt_id} not found for update")
                    return None
                
                conn.commit()
                return self.get_receipt_by_id(receipt_id)
                
        except Exception as e:
            logger.error(f"Failed to update receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to update receipt: {e}") from e

    def delete_receipt(self, receipt_id: int) -> bool:
        """Delete a receipt"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM receipts WHERE id = ?', (receipt_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
                
                if deleted:
                    logger.info(f"Deleted receipt {receipt_id}")
                else:
                    logger.warning(f"Receipt {receipt_id} not found for deletion")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to delete receipt: {e}") from e

    def get_receipt_stats(self) -> Dict[str, Any]:
        """Get receipt statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_receipts,
                        SUM(amount) as total_amount,
                        AVG(amount) as avg_amount,
                        AVG(confidence) as avg_confidence,
                        COUNT(DISTINCT vendor) as unique_vendors,
                        MIN(date) as earliest_date,
                        MAX(date) as latest_date,
                        COUNT(CASE WHEN confidence = 3 THEN 1 END) as high_confidence_count
                    FROM receipts
                ''')
                
                stats = dict(cursor.fetchone())
                
                # Get vendor distribution
                cursor.execute('''
                    SELECT vendor, COUNT(*) as count, SUM(amount) as total
                    FROM receipts
                    WHERE vendor IS NOT NULL
                    GROUP BY vendor
                    ORDER BY count DESC
                    LIMIT 10
                ''')
                stats['top_vendors'] = [dict(row) for row in cursor.fetchall()]
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get receipt stats: {e}")
            raise DatabaseError(f"Failed to get receipt stats: {e}") from e

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert SQLite Row to dictionary with proper type handling"""
        if not row:
            return {}
        
        result = dict(row)
        
        # Parse metadata JSON
        if 'metadata' in result and result['metadata']:
            try:
                result['metadata'] = json.loads(result['metadata'])
            except json.JSONDecodeError:
                result['metadata'] = {}
        
        # Convert date string back to datetime if present
        if 'date' in result and result['date']:
            try:
                result['date'] = datetime.fromisoformat(result['date'])
            except (ValueError, TypeError):
                pass
        
        return result

    def backup(self, backup_path: Union[Path, str]):
        """Create a backup of the database"""
        try:
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(str(backup_path))
                conn.backup(backup_conn)
                backup_conn.close()
                
            logger.info(f"Database backed up to {backup_path}")
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise DatabaseError(f"Backup failed: {e}") from e