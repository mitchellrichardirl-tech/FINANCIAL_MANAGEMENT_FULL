from typing import Optional, Dict, List, Any
from datetime import datetime
import logging
import sqlite3
import json

from src.database.connection import get_manager, DatabaseError, init as initialize_db_connection

logger = logging.getLogger(__name__)


class UploadRepository:
    """Repository for upload CRUD operations."""
    
    def __init__(self):
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
        """
        Create a new upload record.
        
        Args:
            filename: Original filename
            file_type: File type (csv, xlsx, etc.)
            row_count: Number of rows in the file
            column_count: Number of columns
            columns: List of column names
            original_filename: The original name of the uploaded file
            
        Returns:
            ID of the created upload
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
        """
        Get an upload by ID.
        
        Args:
            upload_id: The upload ID
            
        Returns:
            Upload dict or None if not found
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
        """
        Get all uploads with optional filters.
        
        Args:
            limit: Maximum number of results
            offset: Pagination offset
            file_type: Filter by file type
            original_filename: Filter by original filename (partial match)
            filename: Filter by filename (partial match)
            start_date: Filter uploads from this date
            end_date: Filter uploads until this date
            
        Returns:
            List of upload dicts
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
        """
        Update an upload record.
        
        Args:
            upload_id: ID of upload to update
            original_filename: New original filename
            filename: New filename
            file_type: New file type
            row_count: New row count
            column_count: New column count
            columns: New column list
            
        Returns:
            Updated upload dict or None if not found
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
        """
        Delete an upload and all associated data (cascades).
        
        Args:
            upload_id: ID of upload to delete
            
        Returns:
            True if deleted, False if not found
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
        """
        Count uploads with optional filters.
        
        Returns:
            Number of matching uploads
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
        """
        Save uploaded data rows in batches.
        
        Args:
            upload_id: ID of the parent upload
            rows: List of row data dicts
            batch_size: Number of rows to insert per batch
            
        Returns:
            Number of rows inserted
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
        """
        Get uploaded data rows.
        
        Args:
            upload_id: ID of the upload
            limit: Maximum number of rows to return
            offset: Pagination offset
            start_row: Filter rows from this index
            end_row: Filter rows until this index
            
        Returns:
            List of row data dicts
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
        """
        Get a specific row from uploaded data.
        
        Args:
            upload_id: ID of the upload
            row_index: Index of the row
            
        Returns:
            Row data dict or None if not found
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
        """
        Update a specific row in uploaded data.
        
        Args:
            upload_id: ID of the upload
            row_index: Index of the row to update
            row_data: New row data
            
        Returns:
            Updated row dict or None if not found
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
        """
        Delete all data for an upload.
        
        Args:
            upload_id: ID of the upload
            
        Returns:
            Number of rows deleted
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
        """
        Count data rows for an upload.
        
        Args:
            upload_id: ID of the upload
            
        Returns:
            Number of data rows
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
        """
        Create an upload and save all its data in a single transaction.
        
        Args:
            filename: Original filename
            file_type: File type
            columns: List of column names
            rows: List of row data dicts
            batch_size: Batch size for data insertion
            original_filename: The original name of the uploaded file
            
        Returns:
            Dict with upload_id and rows_inserted
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
        """
        Get an upload with its data.
        
        Args:
            upload_id: ID of the upload
            data_limit: Limit for data rows
            data_offset: Offset for data rows
            
        Returns:
            Upload dict with 'data' key containing rows
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
        """
        Get aggregate statistics about uploads.
        
        Returns:
            Dict with upload statistics
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
        """Convert SQLite Row to dictionary with proper type handling."""
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
        """Convert upload_data Row to dictionary with parsed row_data."""
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