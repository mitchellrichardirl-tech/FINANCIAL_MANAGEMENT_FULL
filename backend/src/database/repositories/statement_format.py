"""
Repository for statement format database operations.

Provides CRUD access to the `statement_formats` table through the
`StatementFormatRepository` class. Statement formats describe how to
parse a specific bank's statement export — stored as JSON blobs
conforming to the `StatementConfig` dataclass shape.

The `config_json` column is stored as TEXT but exposed to callers as a
plain dict. Callers should never need to call `json.loads` or
`json.dumps` on these rows — pass dicts in, receive dicts out.

Typical usage:
    repo = StatementFormatRepository()
    fmt = repo.add_format("Chase", "checking", config.to_dict())
    all_formats = repo.get_all_formats()
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional

from src.database.connection import get_manager, DatabaseError, RecordNotFound
from src.database.repositories.base import BaseRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class StatementFormatRepository:
    """Repository for statement format CRUD operations.

    Wraps all database access for the `statement_formats` table behind
    a clean method interface. The `config_json` column is stored as
    serialized JSON but returned to callers as a dict — a malformed row
    is logged and returned with `config_json=None` so that list views
    stay usable even if one row is corrupt.

    Uniqueness is enforced on (bank_name, account_type) at the DB level;
    duplicate inserts raise `DatabaseError`.

    All methods raise `DatabaseError` on failure. Not-found is signaled
    by returning None (reads) or False (deletes), matching the
    `AccountRepository` convention.

    Attributes:
        db: The `ConnectionManager` used for database access.
        br: A `BaseRepository` instance providing shared query helpers.
    """

    def __init__(self):
        """Initialize the repository.

        Retrieves the module-level `ConnectionManager` via `get_manager()`.
        Must be called after `connection.init()` or `connection.init_app()`.
        """
        self.db = get_manager()
        self.br = BaseRepository()

    # ========== Row mapping ==========

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite row to a plain dict, parsing config_json.

        A malformed `config_json` is logged and returned as None rather
        than raising, so that listing endpoints don't blow up on a
        single bad row. Callers that need strict handling should check
        `config_json is not None` after calling `get_format_by_id`.
        """
        d = dict(row)
        raw = d.get("config_json")
        try:
            d["config_json"] = json.loads(raw) if raw else None
        except json.JSONDecodeError as e:
            logger.error(
                f"Malformed config_json for statement_format id={d.get('id')}: {e}"
            )
            d["config_json"] = None
        return d

    # ========== Create ==========

    def add_format(
        self,
        bank_name: str,
        account_type: str,
        config_json: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Create a new statement format and return the full record.

        Args:
            bank_name: Human-readable bank name.
            account_type: Account kind (e.g. "current", "credit_card").
            config_json: Dict representation of the `StatementConfig`
                — typically produced by `StatementConfig.to_dict()`.
                Serialized to JSON for storage.

        Returns:
            Dict of the newly created row, with `config_json` already
            deserialized. None if the row could not be retrieved after
            insert.

        Raises:
            DatabaseError: If a format with the same bank and account
                type already exists, the dict isn't JSON-serializable,
                or the insert fails for any other reason.
        """
        logger.debug(f"Adding statement format: {bank_name} / {account_type}")

        try:
            serialized = json.dumps(config_json)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize config_json: {e}")
            raise DatabaseError(f"Invalid config_json: {e}") from e

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """INSERT INTO statement_formats
                       (bank_name, account_type, config_json)
                       VALUES (?, ?, ?)""",
                    (bank_name, account_type, serialized),
                )
                format_id = cursor.lastrowid

                cursor.execute(
                    "SELECT * FROM statement_formats WHERE id = ?",
                    (format_id,),
                )
                row = cursor.fetchone()

            logger.info(
                f"Added statement format {format_id}: "
                f"{bank_name} / {account_type}"
            )
            return self._row_to_dict(row) if row else None

        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                logger.warning(
                    f"Duplicate statement format: {bank_name} / {account_type}"
                )
                raise DatabaseError(
                    f"Statement format already exists: "
                    f"{bank_name} / {account_type}"
                ) from e
            logger.error(f"Integrity error adding statement format: {e}")
            raise DatabaseError(f"Failed to add statement format: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add statement format: {e}")
            raise DatabaseError(f"Failed to add statement format: {e}") from e

    # ========== Read ==========

    def get_format_by_id(self, format_id: int) -> Dict[str, Any]:
        """Retrieve a single statement format by its primary key.

        Args:
            format_id: The format's `id` value.

        Returns:
            Dict of the format row with `config_json` deserialized.

        Raises:
            RecordNotFound: If no format exists with the given ID.
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM statement_formats WHERE id = ?",
                    (format_id,),
                )
                row = cursor.fetchone()

            if row is None:
                logger.debug(f"Statement format {format_id} not found")
                raise RecordNotFound("StatementFormat", id=format_id)

            return self._row_to_dict(row)

        except RecordNotFound:
            raise
        except Exception as e:
            logger.error(f"Failed to get statement format {format_id}: {e}")
            raise DatabaseError(f"Failed to get statement format: {e}") from e

    def get_format_by_bank_and_type(
        self,
        bank_name: str,
        account_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a format by its (bank_name, account_type) pair.

        Useful for collision checks before insert — the same pair is
        enforced UNIQUE at the DB level, but checking first lets the
        API layer return a clean 409 rather than surfacing a raw
        IntegrityError.

        Args:
            bank_name: The bank name to match.
            account_type: The account type to match.

        Returns:
            Dict of the format row, or None if no match is found.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM statement_formats
                       WHERE bank_name = ? AND account_type = ?""",
                    (bank_name, account_type),
                )
                row = cursor.fetchone()

                if not row:
                    logger.debug(
                        f"Statement format not found: "
                        f"{bank_name} / {account_type}"
                    )
                    return None
                return self._row_to_dict(row)

        except Exception as e:
            logger.error(
                f"Failed to get statement format "
                f"'{bank_name}/{account_type}': {e}"
            )
            raise DatabaseError(f"Failed to get statement format: {e}") from e

    def get_all_formats(self) -> List[Dict[str, Any]]:
        """Retrieve all statement formats, ordered by bank then account type.

        Returns:
            List of format dicts. Empty list if no formats exist.
            Malformed rows are included but with `config_json=None`;
            the registry layer is responsible for skipping them in
            listing views.

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT * FROM statement_formats
                       ORDER BY bank_name, account_type"""
                )
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} statement formats")
                return [self._row_to_dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all statement formats: {e}")
            raise DatabaseError(f"Failed to get statement formats: {e}") from e

    # ========== Update ==========

    def update_format(
        self,
        format_id: int,
        bank_name: Optional[str] = None,
        account_type: Optional[str] = None,
        config_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a statement format's fields selectively.

        Only fields passed with non-None values are modified. The
        `updated_at` column is refreshed on any successful update.
        `config_json` is a full replacement, not a merge — the caller
        is responsible for loading, modifying, and resubmitting the
        complete dict.

        Args:
            format_id: The ID of the format to update.
            bank_name: New bank name. The (bank_name, account_type)
                pair must remain unique.
            account_type: New account type.
            config_json: New config dict. Serialized to JSON for
                storage. Pass None to leave the existing config
                untouched.

        Returns:
            Dict of the updated row with `config_json` deserialized,
            or None if no format exists with the given ID.

        Raises:
            DatabaseError: If the new (bank_name, account_type) pair
                conflicts with an existing row, the dict isn't
                JSON-serializable, or the update fails for any other
                reason.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params: list[Any] = []
                updated_fields = []

                if bank_name is not None:
                    updates.append("bank_name = ?")
                    params.append(bank_name)
                    updated_fields.append("bank_name")

                if account_type is not None:
                    updates.append("account_type = ?")
                    params.append(account_type)
                    updated_fields.append("account_type")

                if config_json is not None:
                    try:
                        serialized = json.dumps(config_json)
                    except (TypeError, ValueError) as e:
                        raise DatabaseError(
                            f"Invalid config_json: {e}"
                        ) from e
                    updates.append("config_json = ?")
                    params.append(serialized)
                    updated_fields.append("config_json")

                if not updates:
                    logger.debug(
                        f"No fields to update for statement format {format_id}"
                    )
                    return self.get_format_by_id(format_id)

                # Bump updated_at on any write — SQLite's DEFAULT only
                # fires on INSERT, so UPDATEs must set it explicitly.
                updates.append(
                    "updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"
                )

                params.append(format_id)
                query = (
                    f"UPDATE statement_formats SET {', '.join(updates)} "
                    f"WHERE id = ?"
                )
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(
                        f"Statement format {format_id} not found for update"
                    )
                    return None

            logger.info(
                f"Updated statement format {format_id}: {updated_fields}"
            )
            return self.get_format_by_id(format_id)

        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                logger.warning(
                    f"Duplicate (bank_name, account_type) on update: "
                    f"{bank_name} / {account_type}"
                )
                raise DatabaseError(
                    f"Statement format already exists: "
                    f"{bank_name} / {account_type}"
                ) from e
            logger.error(
                f"Integrity error updating statement format {format_id}: {e}"
            )
            raise DatabaseError(
                f"Failed to update statement format: {e}"
            ) from e
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to update statement format {format_id}: {e}")
            raise DatabaseError(
                f"Failed to update statement format: {e}"
            ) from e

    # ========== Delete ==========

    def delete_format(self, format_id: int) -> bool:
        """Delete a statement format by ID.

        Note:
            There is no referential integrity check here — the
            `accounts.statement_format` column is a free-form string,
            not a foreign key. If you later add a FK (or start storing
            tagged identifiers like "user:42" and want to block
            deletion of formats still in use), add a pre-delete count
            here following the `delete_account` pattern.

        Args:
            format_id: The ID of the format to delete.

        Returns:
            True if the format was deleted, False if no format exists
            with the given ID.

        Raises:
            DatabaseError: If the delete fails.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM statement_formats WHERE id = ?",
                    (format_id,),
                )

                if cursor.rowcount == 0:
                    logger.debug(
                        f"Statement format {format_id} not found for deletion"
                    )
                    return False

                logger.info(f"Deleted statement format {format_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete statement format {format_id}: {e}")
            raise DatabaseError(
                f"Failed to delete statement format: {e}"
            ) from e

    # ========== Utility ==========

    def count_formats(self) -> int:
        """Return the number of user-defined statement formats.

        Useful for the empty-state check in the UI (and for tests).

        Raises:
            DatabaseError: If the query fails.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as count FROM statement_formats"
                )
                row = cursor.fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"Failed to count statement formats: {e}")
            raise DatabaseError(
                f"Failed to count statement formats: {e}"
            ) from e