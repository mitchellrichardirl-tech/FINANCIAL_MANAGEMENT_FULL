"""
Database connection management for SQLite.

This module provides connection management for the application's SQLite database,
including a `ConnectionManager` class for standalone use and Flask integration
helpers that tie connection lifecycle to the request context.

Typical usage (standalone):
    from src.database.connection import init, get_manager

    init("path/to/data.db")
    manager = get_manager()
    with manager.transaction() as conn:
        conn.execute("INSERT INTO ...")

Typical usage (Flask):
    from src.database.connection import init_app, get_db

    # In app factory
    init_app(app)

    # In a route
    db = get_db()
    rows = db.execute("SELECT ...").fetchall()
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

from flask import current_app, g

from src.database.migrations import migrate
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class DatabaseError(Exception):
    """Raised when a database operation fails.

    Wraps lower-level `sqlite3.Error` exceptions and other failures
    (e.g. backup I/O errors) with a consistent exception type so callers
    can catch a single error class.
    """

    pass

class RecordNotFound(DatabaseError):
    """Requested record does not exist. Safe to map to HTTP 404."""
    def __init__(self, entity: str, **criteria):
        self.entity = entity
        self.criteria = criteria
        parts = ", ".join(f"{k}={v!r}" for k, v in criteria.items())
        super().__init__(f"{entity} not found: {parts}")

class ConnectionManager:
    """Manages SQLite database connections and configuration.

    Resolves the database path (preferring Flask app config when available),
    ensures the parent directory exists, and provides helpers for opening
    raw connections, scoped connections, and transactions.

    All connections are configured with:
        - `sqlite3.Row` row factory (dict-like row access)
        - Foreign key enforcement enabled
        - WAL journal mode for better concurrent read performance

    Attributes:
        db_path: Resolved `Path` to the SQLite database file.
    """

    def __init__(self, db_path: Union[Path, str] = "data.db"):
        """Initialize the connection manager.

        Attempts to read `DATABASE_PATH` from the current Flask app config.
        Falls back to the provided `db_path` if no app context is active
        or the config key is missing.

        Args:
            db_path: Fallback path to the database file. Used only when
                Flask app config is unavailable. Defaults to "data.db".
        """
        try:
            self.db_path = Path(current_app.config["DATABASE_PATH"])
        except Exception:
            logger.info(f"No app config found, using default db path: {db_path}")
            self.db_path = Path(db_path)

        self._ensure_directory_exists()
        logger.info(f"Connection manager initialized: {self.db_path}")

    def _ensure_directory_exists(self):
        """Create the database file's parent directory if it does not exist.

        No-op if the database path has no parent component (i.e. lives in
        the current working directory).
        """
        if self.db_path.parent != Path("."):
            created = not self.db_path.parent.exists()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            if created:
                logger.info(f"Created database directory: {self.db_path.parent}")

    def get_raw_connection(self) -> sqlite3.Connection:
        """Open and return a new configured database connection.

        The caller is responsible for closing the returned connection.
        Prefer `get_connection()` or `transaction()` for automatic cleanup.

        Returns:
            A new `sqlite3.Connection` with row factory, foreign keys,
            and WAL mode configured.

        Raises:
            DatabaseError: If the connection cannot be established.
        """
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            logger.debug("Opened new database connection")
            return conn
        except sqlite3.Error as e:
            logger.error(f"Connection failed: {e}")
            raise DatabaseError(f"Database connection failed: {e}") from e

    @contextmanager
    def get_connection(self):
        """Context manager that yields a connection and closes it on exit.

        Does not commit or roll back — use `transaction()` if you need
        automatic transaction handling.

        Yields:
            sqlite3.Connection: An open, configured connection.

        Example:
            with manager.get_connection() as conn:
                rows = conn.execute("SELECT * FROM accounts").fetchall()
        """
        conn = self.get_raw_connection()
        try:
            yield conn
        finally:
            conn.close()
            logger.debug("Closed database connection")

    @contextmanager
    def transaction(self):
        """Context manager that wraps a connection in a transaction.

        Commits automatically if the block exits normally; rolls back and
        re-raises if any exception occurs.

        Yields:
            sqlite3.Connection: An open connection inside an implicit
            transaction.

        Raises:
            Exception: Re-raises any exception from the wrapped block
                after rolling back.

        Example:
            with manager.transaction() as conn:
                conn.execute("INSERT INTO accounts (name) VALUES (?)", ("Savings",))
                conn.execute("UPDATE accounts SET active = 1 WHERE name = ?", ("Savings",))
        """
        with self.get_connection() as conn:
            try:
                yield conn
                conn.commit()
                logger.debug("Transaction committed")
            except Exception as e:
                conn.rollback()
                logger.warning(f"Transaction rolled back: {type(e).__name__}: {e}")
                raise

    def backup(self, backup_path: Union[Path, str]):
        """Create a consistent backup of the database using SQLite's backup API.

        Creates parent directories for `backup_path` if they don't exist.
        Safe to call while other connections are reading/writing (WAL mode).

        Args:
            backup_path: Destination path for the backup file. Will be
                overwritten if it already exists.

        Raises:
            DatabaseError: If the backup fails for any reason.
        """
        backup_path = Path(backup_path)

        logger.info(f"Starting database backup to: {backup_path}")

        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            with self.get_connection() as conn:
                backup_conn = sqlite3.connect(str(backup_path))
                conn.backup(backup_conn)
                backup_conn.close()

            logger.info(f"Database backup complete: {backup_path}")

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            raise DatabaseError(f"Backup failed: {e}") from e


# Module-level default instance
_default_manager: Optional[ConnectionManager] = None


def init(db_path: Union[Path, str] = "data.db") -> ConnectionManager:
    """Initialize the module-level default connection manager.

    Replaces any previously initialized manager. Most callers should use
    `init_app()` instead when running under Flask.

    Args:
        db_path: Path to the SQLite database file. Ignored if a Flask
            app context with `DATABASE_PATH` config is active.

    Returns:
        The newly created `ConnectionManager`.
    """
    global _default_manager
    logger.debug(f"Initializing default connection manager: {db_path}")
    _default_manager = ConnectionManager(db_path)
    return _default_manager


def get_manager() -> ConnectionManager:
    """Return the module-level default connection manager.

    Returns:
        The `ConnectionManager` created by `init()` or `init_app()`.

    Raises:
        DatabaseError: If neither `init()` nor `init_app()` has been called.
    """
    if os.environ.get("PDOC_GENERATING"):
        from unittest.mock import MagicMock

        logger.warning(
            "PDOC_GENERATING detected, returning MagicMock for ConnectionManager"
        )
        return MagicMock(spec=ConnectionManager)
    if _default_manager is None:
        logger.error("Connection manager accessed before initialization")
        raise DatabaseError("Connection manager not initialized. Call init() first.")
    return _default_manager


def close_manager():
    """Reset the module-level default connection manager to None.

    Does not close any open connections — callers are responsible for
    ensuring connections are closed before calling this. Primarily useful
    in tests to reset module state between runs.
    """
    global _default_manager
    _default_manager = None
    logger.info("Default connection manager closed")


# =============================================================================
# Flask Integration
# =============================================================================


def init_app(app, create_tables=True):
    """Bind the database layer to a Flask application.

    Reads `DATABASE_PATH` from app config, initializes the default
    connection manager, registers a teardown handler to close the
    per-request connection, and optionally creates the schema and runs
    migrations.

    The manager is also attached to the app as `app.db_manager` for
    direct access outside a request context.

    Args:
        app: The Flask application instance.
        create_tables: If True (default), run `SchemaManager.init_db()`
            and apply pending migrations. Set to False for tests or
            read-only deployments.

    Returns:
        The initialized `ConnectionManager`.
    """
    db_path = app.config.get("DATABASE_PATH", "data/app.db")
    logger.info(f"Initializing database for Flask app: {db_path}")

    manager = init(db_path)
    app.db_manager = manager
    app.teardown_appcontext(teardown_db)

    if create_tables:
        from src.database.schema import SchemaManager

        schema_manager = SchemaManager(manager)
        schema_manager.init_db()
        logger.debug("Database schema initialized")
        migrate(db_path)
        logger.debug("Database migrations applied")

    else:
        logger.debug("Skipping table creation (create_tables=False)")

    return manager


def teardown_db(exception=None):
    """Close the per-request database connection, if one was opened.

    Registered as a Flask `teardown_appcontext` callback by `init_app()`
    and invoked automatically at the end of each request.

    Args:
        exception: The unhandled exception that ended the request, if any.
            Passed by Flask; unused here.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_db() -> sqlite3.Connection:
    """Return the database connection for the current Flask request.

    Opens a new connection on first call within a request and caches it on
    `flask.g`. Subsequent calls in the same request return the same
    connection. The connection is closed automatically by `teardown_db()`
    when the request ends.

    Must be called within a Flask application/request context.

    Returns:
        The request-scoped `sqlite3.Connection`.

    Raises:
        DatabaseError: If the connection manager has not been initialized.
    """
    if "db" not in g:
        manager = get_manager()
        g.db = manager.get_raw_connection()
    return g.db


def get_db_transaction():
    """Return the request-scoped connection for manual transaction control.

    Thin wrapper around `get_db()` provided for readability at call sites
    that perform multi-statement writes. The caller is responsible for
    calling `commit()` on success and `rollback()` on failure.

    Returns:
        The request-scoped `sqlite3.Connection`.

    Example:
        db = get_db_transaction()
        try:
            db.execute("INSERT INTO ...")
            db.execute("UPDATE ...")
            db.commit()
        except Exception:
            db.rollback()
            raise
    """
    return get_db()
