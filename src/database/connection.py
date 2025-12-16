from pathlib import Path
from typing import Union, Optional
from contextlib import contextmanager
import sqlite3
import logging

from flask import current_app, g

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


class ConnectionManager:
    """Manages SQLite database connections and configuration."""
    
    def __init__(self, db_path: Union[Path, str] = "data.db"):
        try:
            self.db_path = current_app.config['DATABASE_PATH']
        except Exception as e:
            logger.info(f"No database path found in app config so using default database location: {db_path}")
            self.db_path = Path(db_path)
        self._ensure_directory_exists()
        logger.info(f"Database initialized at {self.db_path}")
    
    def _ensure_directory_exists(self):
        """Ensure the directory for the database exists."""
        if self.db_path.parent != Path('.'):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_raw_connection(self) -> sqlite3.Connection:
        """Get a new database connection."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise DatabaseError(f"Database connection failed: {e}") from e
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = self.get_raw_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self):
        """Context manager that auto-commits on success, rolls back on error."""
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def backup(self, backup_path: Union[Path, str]):
        """Create a backup of the database."""
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


# Module-level default instance
_default_manager: Optional[ConnectionManager] = None


def init(db_path: Union[Path, str] = "data.db") -> ConnectionManager:
    """Initialize the default connection manager."""
    global _default_manager
    _default_manager = ConnectionManager(db_path)
    return _default_manager


def get_manager() -> ConnectionManager:
    """Get the default connection manager."""
    if _default_manager is None:
        raise DatabaseError("Connection manager not initialized. Call init() first.")
    return _default_manager


def close_manager():
    """Close/reset the default connection manager."""
    global _default_manager
    _default_manager = None


# =============================================================================
# Flask Integration
# =============================================================================

def init_app(app, create_tables=True):
    """
    Initialize database with Flask application.
    
    Args:
        app: Flask application instance
        create_tables: Whether to create tables (default True)
    """
    db_path = app.config.get('DATABASE_PATH', 'data/app.db')
    logger.debug(f"Initializing app in connection - db path is {db_path}")
    # Initialize the global manager
    manager = init(db_path)
    
    # Store reference on app
    app.db_manager = manager
    
    # Register teardown
    app.teardown_appcontext(teardown_db)
    
    # Create tables if requested
    if create_tables:
        from src.database.schema import SchemaManager
        schema_manager = SchemaManager(manager)
        schema_manager.init_db()
    
    logger.info(f"Database initialized for Flask app: {db_path}")
    
    return manager

def teardown_db(exception=None):
    """
    Close database connection at end of request.
    
    Called automatically by Flask.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_db() -> sqlite3.Connection:
    """
    Get database connection for current request.
    
    Creates a new connection if one doesn't exist for this request.
    Connection is automatically closed at end of request.
    
    Usage in route:
        from src.db.connection import get_db
        
        @app.route('/users')
        def get_users():
            db = get_db()
            cursor = db.execute('SELECT * FROM users')
            return jsonify([dict(row) for row in cursor.fetchall()])
    """
    if 'db' not in g:
        manager = get_manager()
        g.db = manager.get_raw_connection()
    return g.db


def get_db_transaction():
    """
    Get database connection and start a transaction.
    
    Usage:
        db = get_db_transaction()
        try:
            db.execute('INSERT INTO ...')
            db.execute('UPDATE ...')
            db.commit()
        except:
            db.rollback()
            raise
    """
    db = get_db()
    return db