"""
Repository for file upload and upload-data access.

Provides the `UploadRepository` class, which manages two related tables:

    - `uploads` — metadata about uploaded files (filename, type, shape).
    - `upload_data` — the individual rows from each uploaded file, stored
      as JSON blobs for schema-agnostic access.

Both tables are covered by a single repository because they're always
accessed together: an upload is meaningless without its data, and data
rows always belong to exactly one upload.

The `columns` field on `uploads` and `row_data` on `upload_data` are
stored as JSON and automatically serialized/deserialized by the
repository.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime
import logging
import sqlite3
import json

from src.database.connection import get_manager, DatabaseError, init as initialize_db_connection

# TODO: Use context logger
logger = logging.getLogger(__name__)


class UploadRepository:
    """Data-access layer for the `uploads` and `upload_data` tables.

    Methods are grouped into four sections:
        1. **Upload CRUD** — create/read/update/delete upload metadata.
        2. **Upload Data** — read/write individual rows of imported data.
        3. **Combined** — atomic create-upload-with-data and
           fetch-upload-with-data convenience methods.
        4. **Statistics** — aggregate queries across all uploads.

    Attributes:
        db: The `ConnectionManager` instance used for database access.
    """

    def __init__(self):
        """Initialize with the default connection manager.

        Falls back to creating a new connection manager if none has been
        initialized. This fallback exists because `UploadRepository` may
        be instantiated outside a Flask app context (e.g. in notebooks
        or CLI scripts).
        """
        try:
            self.db = get_manager()
            logger.debug("UploadRepository initialized with database connection")
        except DatabaseError:
            self.db = initialize_db_connection()
            logger.info("New database connection initialized for UploadRepository")

    # =========================================================================
    # Upload CRUD Operations
    # =========================================================================

    def create_upload(
        self,
        filename: str,
        file_type: str,
        row_count: int = 0,
        column_count: int = 0,
        columns: Optional[List[str]] = None,
        original_filename: Optional[str] = None
    ) -> int:
        """Insert a new upload metadata record.

        Records the shape and column names of an uploaded file. The
        actual row data is stored separately via `save_upload_data()`
        or atomically via `create_upload_with_data()`.

        Args:
            filename: Stored/deduplicated filename on disk.
            file_type: File format identifier (e.g. "csv", "xlsx").
            row_count: Number of data rows in the file. Defaults to 0.
            column_count: Number of columns. Defaults to 0.
            columns: List of column header names. Stored as JSON.
            original_filename: Name of the file as uploaded by the user.
                Defaults to `filename` if not provided.

        Returns:
            The `id` of the newly created upload row.

        Raises:
            DatabaseError: On any database failure.
        """
        if original_filename is None:
            original_filename = filename
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                columns_json = json.dumps(columns) if columns else None

                cursor.execute('''
                    INSERT INTO uploads (
                        original_filename, filename, file_type, row_count, column_count, columns
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    original_filename,
                    filename,
                    file_type,
                    row_count,
                    column_count,
                    columns_json
                ))

                upload_id = cursor.lastrowid
                logger.info(f"Created upload {upload_id}: {filename}")
                return upload_id

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error creating upload: {e}")
            raise DatabaseError(f"Failed to create upload: {e}") from e
        except Exception as e:
            logger.error(f"Failed to create upload: {e}")
            raise DatabaseError(f"Failed to create upload: {e}") from e

    def get_upload_by_id(self, upload_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single upload by primary key.

        Args:
            upload_id: The upload's `id` column value.

        Returns:
            Upload metadata as a dict with `columns` parsed from JSON,
            or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,))
                row = cursor.fetchone()
                return self._row_to_dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to get upload: {e}") from e

    def get_all_uploads(
        self,
        limit: int = 50,
        offset: int = 0,
        file_type: Optional[str] = None,
        original_filename: Optional[str] = None,
        filename: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch uploads with optional filtering and pagination.

        All filter arguments are optional and ANDed together. Results
        are ordered by `upload_date` descending (newest first).

        Args:
            limit: Maximum rows to return. Defaults to 50.
            offset: Rows to skip for pagination. Defaults to 0.
            file_type: Exact match on file type (e.g. "csv").
            original_filename: Substring match on original filename.
            filename: Substring match on stored filename.
            start_date: Only return uploads on or after this date.
            end_date: Only return uploads on or before this date.

        Returns:
            List of upload dicts with `columns` parsed from JSON.
            Empty list if no matches.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                conditions = []
                params = []

                if file_type:
                    conditions.append('file_type = ?')
                    params.append(file_type)

                if original_filename:
                    conditions.append('original_filename LIKE ?')
                    params.append(f'%{original_filename}%')

                if filename:
                    conditions.append('filename LIKE ?')
                    params.append(f'%{filename}%')

                if start_date:
                    conditions.append('upload_date >= ?')
                    params.append(start_date.isoformat())

                if end_date:
                    conditions.append('upload_date <= ?')
                    params.append(end_date.isoformat())

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                query = f'''
                    SELECT * FROM uploads 
                    {where_clause}
                    ORDER BY upload_date DESC 
                    LIMIT ? OFFSET ?
                '''
                params.extend([limit, offset])

                cursor.execute(query, params)
                return [self._row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get uploads: {e}")
            raise DatabaseError(f"Failed to get uploads: {e}") from e

    def update_upload(
        self,
        upload_id: int,
        original_filename: Optional[str] = None,
        filename: Optional[str] = None,
        file_type: Optional[str] = None,
        row_count: Optional[int] = None,
        column_count: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on an existing upload record.

        Only non-None arguments are applied. Passing no updatable fields
        is a no-op that returns the current row.

        Args:
            upload_id: Primary key of the upload to update.
            original_filename: New original filename, if changing.
            filename: New stored filename, if changing.
            file_type: New file type, if changing.
            row_count: New row count, if changing.
            column_count: New column count, if changing.
            columns: New column name list, if changing. Stored as JSON.

        Returns:
            The updated upload as a dict, or None if `upload_id` does
            not exist.

        Raises:
            DatabaseError: On any database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []

                if original_filename is not None:
                    updates.append('original_filename = ?')
                    params.append(original_filename)

                if filename is not None:
                    updates.append('filename = ?')
                    params.append(filename)

                if file_type is not None:
                    updates.append('file_type = ?')
                    params.append(file_type)

                if row_count is not None:
                    updates.append('row_count = ?')
                    params.append(row_count)

                if column_count is not None:
                    updates.append('column_count = ?')
                    params.append(column_count)

                if columns is not None:
                    updates.append('columns = ?')
                    params.append(json.dumps(columns))

                if not updates:
                    return self.get_upload_by_id(upload_id)

                params.append(upload_id)

                query = f"UPDATE uploads SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.warning(f"Upload {upload_id} not found for update")
                    return None

            return self.get_upload_by_id(upload_id)

        except Exception as e:
            logger.error(f"Failed to update upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to update upload: {e}") from e

    def delete_upload(self, upload_id: int) -> bool:
        """Delete an upload and all its associated data rows.

        Child rows in `upload_data` are automatically removed by the
        `ON DELETE CASCADE` foreign key constraint.

        Args:
            upload_id: Primary key of the upload to delete.

        Returns:
            True if the upload was deleted, False if it did not exist.

        Raises:
            DatabaseError: On any database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Data will be cascade deleted due to FK constraint
                cursor.execute('DELETE FROM uploads WHERE id = ?', (upload_id,))
                deleted = cursor.rowcount > 0

                if deleted:
                    logger.info(f"Deleted upload {upload_id} and associated data")
                else:
                    logger.warning(f"Upload {upload_id} not found for deletion")

                return deleted

        except Exception as e:
            logger.error(f"Failed to delete upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to delete upload: {e}") from e

    def count_uploads(
        self,
        file_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> int:
        """Count uploads with optional filters.

        Supports the same filter parameters as `get_all_uploads()` for
        use in pagination (total count alongside a paged result set).

        Args:
            file_type: Exact match on file type.
            start_date: Only count uploads on or after this date.
            end_date: Only count uploads on or before this date.

        Returns:
            Number of matching upload rows.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                conditions = []
                params = []

                if file_type:
                    conditions.append('file_type = ?')
                    params.append(file_type)

                if start_date:
                    conditions.append('upload_date >= ?')
                    params.append(start_date.isoformat())

                if end_date:
                    conditions.append('upload_date <= ?')
                    params.append(end_date.isoformat())

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                cursor.execute(f'SELECT COUNT(*) FROM uploads {where_clause}', params)
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Failed to count uploads: {e}")
            raise DatabaseError(f"Failed to count uploads: {e}") from e

    # =========================================================================
    # Upload Data Operations
    # =========================================================================

    def save_upload_data(
        self,
        upload_id: int,
        rows: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> int:
        """Insert row data for an existing upload in batches.

        Each row dict is JSON-serialized and stored with its zero-based
        index. All batches are inserted within a single transaction, so
        either all rows succeed or none do.

        For atomic upload creation + data insertion, prefer
        `create_upload_with_data()`.

        Args:
            upload_id: FK to the parent `uploads` row.
            rows: List of row data dicts (one per source file row).
            batch_size: Rows per `executemany` call. Affects memory
                usage but not transactional behaviour. Defaults to 1000.

        Returns:
            Number of rows inserted.

        Raises:
            DatabaseError: If `upload_id` doesn't exist (FK violation),
                a (upload_id, row_index) pair is duplicated, or on any
                other database failure.
        """
        try:
            total_inserted = 0

            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Process in batches for better performance
                for batch_start in range(0, len(rows), batch_size):
                    batch = rows[batch_start:batch_start + batch_size]

                    data = [
                        (upload_id, idx + batch_start, json.dumps(row))
                        for idx, row in enumerate(batch)
                    ]

                    cursor.executemany('''
                        INSERT INTO upload_data (upload_id, row_index, row_data)
                        VALUES (?, ?, ?)
                    ''', data)

                    total_inserted += len(batch)

                logger.info(f"Saved {total_inserted} rows for upload {upload_id}")
                return total_inserted

        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity error saving upload data: {e}")
            raise DatabaseError(f"Failed to save upload data: {e}") from e
        except Exception as e:
            logger.error(f"Failed to save upload data: {e}")
            raise DatabaseError(f"Failed to save upload data: {e}") from e

    def get_upload_data(
        self,
        upload_id: int,
        limit: Optional[int] = None,
        offset: int = 0,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch data rows for an upload with optional range and pagination.

        Supports two ways to slice the data:
            - `start_row`/`end_row` — filter by `row_index` (inclusive).
            - `limit`/`offset` — SQL-level pagination on the result set.

        Both can be combined (e.g. rows 100–200, page 1 of 50).

        Args:
            upload_id: FK to the parent upload.
            limit: Maximum rows to return. None for all.
            offset: Rows to skip. Only applied when `limit` is set.
            start_row: Minimum `row_index` (inclusive).
            end_row: Maximum `row_index` (inclusive).

        Returns:
            List of dicts with `row_data` parsed from JSON, ordered by
            `row_index` ascending. Empty list if no matches.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                conditions = ['upload_id = ?']
                params = [upload_id]

                if start_row is not None:
                    conditions.append('row_index >= ?')
                    params.append(start_row)

                if end_row is not None:
                    conditions.append('row_index <= ?')
                    params.append(end_row)

                where_clause = f"WHERE {' AND '.join(conditions)}"

                query = f'''
                    SELECT * FROM upload_data 
                    {where_clause}
                    ORDER BY row_index ASC
                '''

                if limit is not None:
                    query += ' LIMIT ? OFFSET ?'
                    params.extend([limit, offset])

                cursor.execute(query, params)
                return [self._data_row_to_dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get upload data for {upload_id}: {e}")
            raise DatabaseError(f"Failed to get upload data: {e}") from e

    def get_upload_data_row(
        self,
        upload_id: int,
        row_index: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single data row by upload ID and row index.

        Args:
            upload_id: FK to the parent upload.
            row_index: Zero-based row position within the upload.

        Returns:
            Row dict with `row_data` parsed from JSON, or None if no
            match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM upload_data 
                    WHERE upload_id = ? AND row_index = ?
                ''', (upload_id, row_index))
                row = cursor.fetchone()
                return self._data_row_to_dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get row {row_index} for upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to get upload data row: {e}") from e

    def update_upload_data_row(
        self,
        upload_id: int,
        row_index: int,
        row_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Replace the contents of a single data row.

        Args:
            upload_id: FK to the parent upload.
            row_index: Zero-based row position to update.
            row_data: New row contents. Replaces the entire previous
                value (not a merge). Stored as JSON.

        Returns:
            The updated row dict, or None if the (upload_id, row_index)
            pair doesn't exist.

        Raises:
            DatabaseError: On any database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE upload_data 
                    SET row_data = ?
                    WHERE upload_id = ? AND row_index = ?
                ''', (json.dumps(row_data), upload_id, row_index))

                if cursor.rowcount == 0:
                    return None

            return self.get_upload_data_row(upload_id, row_index)

        except Exception as e:
            logger.error(f"Failed to update row {row_index} for upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to update upload data row: {e}") from e

    def delete_upload_data(self, upload_id: int) -> int:
        """Delete all data rows for a given upload.

        Removes only the `upload_data` rows — the parent `uploads`
        record is left intact. Use `delete_upload()` to remove both.

        Args:
            upload_id: FK to the parent upload.

        Returns:
            Number of rows deleted.

        Raises:
            DatabaseError: On any database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM upload_data WHERE upload_id = ?', (upload_id,))
                deleted = cursor.rowcount

                logger.info(f"Deleted {deleted} data rows for upload {upload_id}")
                return deleted

        except Exception as e:
            logger.error(f"Failed to delete upload data for {upload_id}: {e}")
            raise DatabaseError(f"Failed to delete upload data: {e}") from e

    def count_upload_data_rows(self, upload_id: int) -> int:
        """Count data rows stored for an upload.

        Useful for verifying completeness against `uploads.row_count`.

        Args:
            upload_id: FK to the parent upload.

        Returns:
            Number of rows in `upload_data` for this upload.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM upload_data WHERE upload_id = ?',
                    (upload_id,)
                )
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Failed to count data rows for upload {upload_id}: {e}")
            raise DatabaseError(f"Failed to count upload data: {e}") from e

    # =========================================================================
    # Combined Operations
    # =========================================================================

    def create_upload_with_data(
        self,
        filename: str,
        file_type: str,
        columns: List[str],
        rows: List[Dict[str, Any]],
        batch_size: int = 1000,
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an upload record and insert all its data atomically.

        Wraps the upload creation and data insertion in a single
        transaction, so a failure at any point rolls back everything.
        Preferred over calling `create_upload()` + `save_upload_data()`
        separately.

        Args:
            filename: Stored/deduplicated filename on disk.
            file_type: File format identifier (e.g. "csv", "xlsx").
            columns: List of column header names.
            rows: List of row data dicts. `row_count` and
                `column_count` are derived automatically.
            batch_size: Rows per `executemany` call. Defaults to 1000.
            original_filename: Name as uploaded by the user. Defaults
                to `filename` if not provided.

        Returns:
            Dict with `upload_id` and `rows_inserted`.

        Raises:
            DatabaseError: On any database failure (entire operation is
                rolled back).
        """
        if original_filename is None:
            original_filename = filename
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Create upload record
                columns_json = json.dumps(columns)
                cursor.execute('''
                    INSERT INTO uploads (
                        original_filename, filename, file_type, row_count, column_count, columns
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    original_filename,
                    filename,
                    file_type,
                    len(rows),
                    len(columns),
                    columns_json
                ))

                upload_id = cursor.lastrowid

                # Insert data in batches
                for batch_start in range(0, len(rows), batch_size):
                    batch = rows[batch_start:batch_start + batch_size]

                    data = [
                        (upload_id, idx + batch_start, json.dumps(row))
                        for idx, row in enumerate(batch)
                    ]

                    cursor.executemany('''
                        INSERT INTO upload_data (upload_id, row_index, row_data)
                        VALUES (?, ?, ?)
                    ''', data)

                logger.info(f"Created upload {upload_id} with {len(rows)} rows")

                return {
                    'upload_id': upload_id,
                    'rows_inserted': len(rows)
                }

        except Exception as e:
            logger.error(f"Failed to create upload with data: {e}")
            raise DatabaseError(f"Failed to create upload with data: {e}") from e

    def get_upload_with_data(
        self,
        upload_id: int,
        data_limit: Optional[int] = None,
        data_offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Fetch an upload's metadata and its data rows together.

        Convenience method that combines `get_upload_by_id()` and
        `get_upload_data()` into a single call. The data rows are
        nested under a `data` key on the returned dict.

        Args:
            upload_id: Primary key of the upload.
            data_limit: Maximum data rows to include. None for all.
            data_offset: Pagination offset for data rows.

        Returns:
            Upload metadata dict with an added `data` key containing
            the list of row dicts, or None if the upload doesn't exist.
        """
        upload = self.get_upload_by_id(upload_id)

        if upload is None:
            return None

        upload['data'] = self.get_upload_data(
            upload_id,
            limit=data_limit,
            offset=data_offset
        )

        return upload

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_upload_stats(self) -> Dict[str, Any]:
        """Compute aggregate statistics across all uploads.

        Returns:
            Dict with these keys:
                - `total_uploads`: Total number of upload records.
                - `total_rows`: Sum of `row_count` across all uploads.
                - `avg_rows_per_upload`: Mean rows per upload.
                - `avg_columns`: Mean column count per upload.
                - `earliest_upload`, `latest_upload`: Date range.
                - `by_file_type`: List of dicts with `file_type`,
                  `count`, and `total_rows` per type.
                - `recent_uploads`: Up to 10 most recent uploads with
                  `id`, `filename`, `file_type`, `row_count`, and
                  `upload_date`.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Overall stats
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_uploads,
                        SUM(row_count) as total_rows,
                        AVG(row_count) as avg_rows_per_upload,
                        AVG(column_count) as avg_columns,
                        MIN(upload_date) as earliest_upload,
                        MAX(upload_date) as latest_upload
                    FROM uploads
                ''')
                stats = dict(cursor.fetchone())

                # By file type
                cursor.execute('''
                    SELECT 
                        file_type,
                        COUNT(*) as count,
                        SUM(row_count) as total_rows
                    FROM uploads
                    GROUP BY file_type
                    ORDER BY count DESC
                ''')
                stats['by_file_type'] = [dict(row) for row in cursor.fetchall()]

                # Recent uploads
                cursor.execute('''
                    SELECT id, filename, file_type, row_count, upload_date
                    FROM uploads
                    ORDER BY upload_date DESC
                    LIMIT 10
                ''')
                stats['recent_uploads'] = [dict(row) for row in cursor.fetchall()]

                return stats

        except Exception as e:
            logger.error(f"Failed to get upload stats: {e}")
            raise DatabaseError(f"Failed to get upload stats: {e}") from e

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert an `uploads` row to a dict with deserialized `columns`.

        Parses the `columns` JSON field back into a list. Falls back to
        an empty list on parse failure.

        Args:
            row: Row from a `SELECT * FROM uploads` query.

        Returns:
            Dict representation of the row. Empty dict if `row` is None.
        """
        if not row:
            return {}

        result = dict(row)

        # Parse columns JSON
        if 'columns' in result and result['columns']:
            try:
                result['columns'] = json.loads(result['columns'])
            except json.JSONDecodeError:
                result['columns'] = []

        return result

    def _data_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert an `upload_data` row to a dict with deserialized `row_data`.

        Parses the `row_data` JSON field back into a dict. Falls back to
        an empty dict on parse failure.

        Args:
            row: Row from a `SELECT * FROM upload_data` query.

        Returns:
            Dict representation of the row. Empty dict if `row` is None.
        """
        if not row:
            return {}

        result = dict(row)

        # Parse row_data JSON
        if 'row_data' in result and result['row_data']:
            try:
                result['row_data'] = json.loads(result['row_data'])
            except json.JSONDecodeError:
                result['row_data'] = {}

        return result