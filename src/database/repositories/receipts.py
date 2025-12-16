from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
import logging
import sqlite3
import json

from src.database.connection import get_manager, DatabaseError, init as initialize_db_connection
from src.models.receipt import Receipt

_UNSET = object()

logger = logging.getLogger(__name__)


class ReceiptRepository:
    """Repository for receipt CRUD operations"""
    
    def __init__(self):
        try:
            self.db = get_manager()
            logger.debug("ReceiptRepository initialized with database connection")
        except DatabaseError:
            self.db = initialize_db_connection()
            logger.info("New database connection initialized for ReceiptRepository")
             
    def save(self, receipt: Receipt) -> int|None:
        """Save receipt to database"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                metadata = {
                    'selected_method': receipt.selected_method,
                    'page_number': receipt.page_number,
                }
                
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
                    str(receipt.original_filename),
                    receipt.stored_filename,
                    str(receipt.file_path) if receipt.file_path else None,
                    receipt.vendor,
                    receipt.amount,
                    date_str,
                    receipt.confidence,
                    receipt.selected_method,
                    receipt.extracted_text,
                    json.dumps(metadata)
                ))
                
                receipt_id = cursor.lastrowid
                logger.info(f"Saved receipt {receipt_id}: {receipt.original_filename}")
                return receipt_id
                
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg or "duplicate" in error_msg:
                logger.error(f"Receipt already exists: {e}")
                raise DatabaseError(f"Receipt already exists: {receipt.stored_filename}") from e
            elif "not null" in error_msg:
                logger.error(f"Missing required field: {e}")
                raise DatabaseError(f"Missing required field: {e}") from e
            else:
                logger.error(f"Integrity error: {e}")
                raise DatabaseError(f"Database integrity error: {e}") from e
        except Exception as e:
            logger.error(f"Failed to save receipt: {e}")
            raise DatabaseError(f"Failed to save receipt: {e}") from e
    
    def get_all(
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
            with self.db.get_connection() as conn:
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
                return [self._row_to_dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get receipts: {e}")
            raise DatabaseError(f"Failed to get receipts: {e}") from e
    
    def get_by_id(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific receipt"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,))
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to get receipt: {e}") from e
    
    def update(
        self,
        id: int,
        vendor: Optional[str] = _UNSET,  # type: ignore
        amount: Optional[float] = _UNSET,  # type: ignore
        date: Optional[datetime] = _UNSET,  # type: ignore
        confidence: Optional[int] = _UNSET,  # type: ignore
        raw_text: Optional[str] = _UNSET  # type: ignore
    ) -> Optional[Dict[str, Any]]:
        """Update receipt data"""
        logger.debug(f'Updating receipt {id}')
        try:
            with self.db.transaction() as conn:
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
                    if date is not None:
                        date_str = date.date().isoformat() if isinstance(date, datetime) else str(date)
                    else:
                        date_str = None
                    params.append(date_str)
                
                if confidence is not _UNSET:
                    updates.append('confidence = ?')
                    params.append(confidence)
                
                if raw_text is not _UNSET:
                    updates.append('raw_text = ?')
                    params.append(raw_text)
                
                if not updates:
                    return self.get_by_id(id)
                
                params.append(id)
                
                query = f"UPDATE receipts SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Receipt {id} not found for update")
                    return None
                logger.debug(f'Updated receipt {id}')
            return self.get_by_id(id)
                
        except Exception as e:
            logger.error(f"Failed to update receipt {id}: {e}")
            raise DatabaseError(f"Failed to update receipt: {e}") from e
    
    def delete(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Delete a receipt"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                receipt_to_delete = self.get_by_id(receipt_id)
                cursor.execute('DELETE FROM receipts WHERE id = ?', (receipt_id,))
                deleted = cursor.rowcount > 0
                
                if deleted:
                    logger.info(f"Deleted receipt {receipt_id}")
                    return receipt_to_delete
                raise DatabaseError(f"Receipt {receipt_id} not found for deletion")
                
        except Exception as e:
            logger.error(f"Failed to delete receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to delete receipt: {e}") from e
    
    def get_stats(self) -> Dict[str, Any]:
        """Get receipt statistics"""
        try:
            with self.db.get_connection() as conn:
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
        
        if 'metadata' in result and result['metadata']:
            try:
                result['metadata'] = json.loads(result['metadata'])
            except json.JSONDecodeError:
                result['metadata'] = {}
        
        if 'date' in result and result['date']:
            try:
                result['date'] = datetime.fromisoformat(result['date'])
            except (ValueError, TypeError):
                pass
        
        return result