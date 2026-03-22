"""
Repository for receipt data access.

Provides the `ReceiptRepository` class, which handles CRUD and aggregate
queries against the `receipts` table. Receipts store extracted metadata
from uploaded receipt images (vendor, amount, date, confidence) along
with the raw OCR output.

Unlike other repositories, `update()` uses a sentinel-based API so that
callers can explicitly set a field to None (e.g. clear an incorrect
vendor extraction) rather than None meaning "don't change".
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import sqlite3
import json

from src.database.connection import get_manager, DatabaseError
from src.models.receipt import Receipt
from src.utils.logging import ContextLogger

# Sentinel for update(): distinguishes "not provided" from "set to None".
_UNSET = object()

logger = ContextLogger(__name__)


class ReceiptRepository:
    """Data-access layer for the `receipts` table.

    Accepts `Receipt` model instances on save and returns plain dicts
    on read. The `metadata` column is stored as JSON and automatically
    serialized/deserialized. Date strings are parsed back into
    `datetime` objects on read.

    Attributes:
        db: The default `ConnectionManager` instance.
    """

    def __init__(self):
        """Initialize with the default connection manager.

        Raises:
            DatabaseError: If the connection manager has not been
                initialized via `connection.init()` / `init_app()`.
        """
        self.db = get_manager()

    def save(self, receipt: Receipt) -> int | None:
        """Insert a new receipt row from a `Receipt` model instance.

        Serializes `selected_method` and `page_number` into the
        `metadata` JSON column, and normalises the date to ISO format.

        Args:
            receipt: Populated `Receipt` model. The `stored_filename`
                must be unique.

        Returns:
            The `id` of the newly created receipt row.

        Raises:
            DatabaseError: If `stored_filename` already exists, a
                required field is missing, or on any other database
                failure.
        """
        logger.debug(f"Saving receipt: {receipt.original_filename}")

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

                logger.info(
                    f"Saved receipt {receipt_id}: {receipt.original_filename} "
                    f"| vendor={receipt.vendor}, confidence={receipt.confidence}"
                )
                return receipt_id

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg or "duplicate" in error_msg:
                logger.warning(f"Duplicate receipt: {receipt.stored_filename}")
                raise DatabaseError(f"Receipt already exists: {receipt.stored_filename}") from e
            elif "not null" in error_msg:
                logger.warning(f"Missing required field: {e}")
                raise DatabaseError(f"Missing required field: {e}") from e
            else:
                logger.error(f"Integrity error saving receipt: {e}")
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
        """Fetch receipts with optional filtering and pagination.

        All filter arguments are optional and ANDed together. Results
        are ordered by `created_at` descending (newest first).

        Args:
            limit: Maximum rows to return. Defaults to 50.
            offset: Rows to skip for pagination. Defaults to 0.
            vendor: Substring match against vendor name (SQL LIKE,
                case-insensitive on most SQLite builds).
            min_confidence: Only return receipts with confidence >= this
                value (0–3).
            start_date: Only return receipts dated on or after this date.
            end_date: Only return receipts dated on or before this date.

        Returns:
            List of receipt dicts with `metadata` parsed from JSON and
            `date` as a `datetime`. Empty list if no matches.

        Raises:
            DatabaseError: On query failure.
        """
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

                if conditions:
                    logger.debug(f"Querying receipts with {len(conditions)} filters")

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

                logger.debug(
                    f"Retrieved {len(receipts)} receipts "
                    f"(offset={offset}, limit={limit})"
                )
                return receipts

        except Exception as e:
            logger.error(f"Failed to get receipts: {e}")
            raise DatabaseError(f"Failed to get receipts: {e}") from e

    def get_by_id(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single receipt by primary key.

        Args:
            receipt_id: The receipt's `id` column value.

        Returns:
            The receipt as a dict with `metadata` parsed from JSON and
            `date` as a `datetime`, or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Receipt {receipt_id} not found")
                    return None

                return self._row_to_dict(row)

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
        """Update one or more fields on an existing receipt.

        Uses a sentinel default (`_UNSET`) so that `None` is a valid
        value to write. This lets callers explicitly clear a field —
        e.g. `update(id, vendor=None)` nulls the vendor — while omitted
        arguments are left unchanged.

        Args:
            id: Primary key of the receipt to update.
            vendor: New vendor name. Pass None to clear.
            amount: New amount. Pass None to clear.
            date: New receipt date. Pass None to clear.
            confidence: New confidence score (0–3). Pass None to clear.
            raw_text: New OCR text. Pass None to clear.

        Returns:
            The updated receipt as a dict, or None if `id` does not
            exist.

        Raises:
            DatabaseError: On any database failure, including check
                constraint violations (e.g. amount < 0, confidence
                outside 0–3).
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if vendor is not _UNSET:
                    updates.append('vendor = ?')
                    params.append(vendor)
                    updated_fields.append('vendor')

                if amount is not _UNSET:
                    updates.append('amount = ?')
                    params.append(amount)
                    updated_fields.append('amount')

                if date is not _UNSET:
                    updates.append('date = ?')
                    if date is not None:
                        date_str = date.date().isoformat() if isinstance(date, datetime) else str(date)
                    else:
                        date_str = None
                    params.append(date_str)
                    updated_fields.append('date')

                if confidence is not _UNSET:
                    updates.append('confidence = ?')
                    params.append(confidence)
                    updated_fields.append('confidence')

                if raw_text is not _UNSET:
                    updates.append('raw_text = ?')
                    params.append(raw_text)
                    updated_fields.append('raw_text')

                if not updates:
                    logger.debug(f"No fields to update for receipt {id}")
                    return self.get_by_id(id)

                params.append(id)

                query = f"UPDATE receipts SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Receipt {id} not found for update")
                    return None

            logger.info(f"Updated receipt {id}: {updated_fields}")
            return self.get_by_id(id)

        except Exception as e:
            logger.error(f"Failed to update receipt {id}: {e}")
            raise DatabaseError(f"Failed to update receipt: {e}") from e

    def delete(self, receipt_id: int) -> Optional[Dict[str, Any]]:
        """Delete a receipt and return the deleted row.

        Fetches the row before deleting so callers (e.g. the API layer)
        can report what was removed. Linked transactions have their
        `receipt_id` set to NULL via the `ON DELETE SET NULL` foreign
        key — deleting a receipt never orphans or blocks on transactions.

        Args:
            receipt_id: Primary key of the receipt to delete.

        Returns:
            The deleted receipt as a dict, or None if `receipt_id` did
            not exist.

        Raises:
            DatabaseError: On any database failure.
        """
        try:
            # Fetch before delete (outside transaction is fine for read)
            receipt_to_delete = self.get_by_id(receipt_id)

            if not receipt_to_delete:
                logger.debug(f"Receipt {receipt_id} not found for deletion")
                return None

            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM receipts WHERE id = ?', (receipt_id,))

            logger.info(f"Deleted receipt {receipt_id}")
            return receipt_to_delete

        except Exception as e:
            logger.error(f"Failed to delete receipt {receipt_id}: {e}")
            raise DatabaseError(f"Failed to delete receipt: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics across all receipts.

        Returns:
            Dict with these keys:
                - `total_receipts`: Row count.
                - `total_amount`: Sum of all amounts.
                - `avg_amount`: Mean amount.
                - `avg_confidence`: Mean extraction confidence.
                - `unique_vendors`: Count of distinct vendor names.
                - `earliest_date`, `latest_date`: Date range (as strings).
                - `high_confidence_count`: Receipts with confidence = 3.
                - `top_vendors`: Up to 10 dicts of `{vendor, count, total}`
                  ordered by receipt count descending.

        Raises:
            DatabaseError: On query failure.
        """
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

                logger.debug(f"Retrieved stats: {stats.get('total_receipts', 0)} total receipts")
                return stats

        except Exception as e:
            logger.error(f"Failed to get receipt stats: {e}")
            raise DatabaseError(f"Failed to get receipt stats: {e}") from e

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a `sqlite3.Row` to a dict with deserialized fields.

        Parses the `metadata` column from JSON (falling back to an empty
        dict on parse failure) and converts the `date` column from ISO
        string back to `datetime` (leaving it as-is on parse failure).

        Args:
            row: Row from a `SELECT * FROM receipts` query.

        Returns:
            Dict representation of the row. Empty dict if `row` is None.
        """
        if not row:
            return {}

        result = dict(row)

        if 'metadata' in result and result['metadata']:
            try:
                result['metadata'] = json.loads(result['metadata'])
            except json.JSONDecodeError:
                logger.debug(f"Failed to parse metadata for receipt {result.get('id')}")
                result['metadata'] = {}

        if 'date' in result and result['date']:
            try:
                result['date'] = datetime.fromisoformat(result['date'])
            except (ValueError, TypeError):
                logger.debug(
                    f"Failed to parse date for receipt {result.get('id')}: "
                    f"{result['date']!r}"
                )

        return result