"""
Repository for the four-level category hierarchy.

Manages CRUD operations across the full hierarchy:

    categories → sub_categories → types → parties

All four tables are accessed through a single `CategoryRepository` class
because operations frequently span levels (e.g. remapping a party to a
new type, ensuring the "Unknown" fallback hierarchy exists, building
alias mappings that join parties back to transactions).

Party alias resolution and the "Unknown" auto-creation logic also live
here since they're tightly coupled to the hierarchy.
"""

from typing import Optional, Dict, List, Any, Union
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.base import BaseRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class CategoryRepository:
    """Data-access layer for the category hierarchy tables.

    Covers four tables — `categories`, `sub_categories`, `types`, and
    `parties` — plus cross-cutting concerns like party remapping, alias
    resolution, and the auto-created "Unknown" fallback hierarchy.

    Methods are grouped by table, then by CRUD operation, with hierarchy
    and utility methods at the end.

    Attributes:
        db: The default `ConnectionManager` instance.
        br: Shared `BaseRepository` helper for common query patterns.
        _unknown_type_id: Cached ID of the "Unknown" type. Populated
            lazily by `_ensure_unknown_hierarchy()` on first use.
    """

    def __init__(self):
        """Initialize with the default connection manager.

        Raises:
            DatabaseError: If the connection manager has not been
                initialized via `connection.init()` / `init_app()`.
        """
        self.db = get_manager()
        self.br = BaseRepository()
        self._unknown_type_id = None

    # ========== Categories ==========

    def add_category(self, category: str, description: Optional[str] = None) -> Union[int, None]:
        """Insert a new top-level category.

        Args:
            category: Unique category name (e.g. "Housing", "Food").
            description: Optional human-readable description.

        Returns:
            The `id` of the newly created category.

        Raises:
            DatabaseError: If a category with the same name already
                exists, or on any other database failure.
        """
        logger.debug(f"Adding category: {category}")

        try:
            category_id = self.br.insert_query(
                "INSERT INTO categories (category, description) VALUES (?, ?)",
                (category, description)
            )
            logger.info(f"Added category {category_id}: {category}")
            return category_id

        # TODO: This error will never be reached as it's caught by the
        # BaseRepository. Refactor to let it bubble up and avoid double-logging.
        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                logger.warning(f"Duplicate category: {category}")
                raise DatabaseError(f"Category already exists: {category}") from e
            logger.error(f"Integrity error adding category: {e}")
            raise DatabaseError(f"Failed to add category: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add category: {e}")
            raise DatabaseError(f"Failed to add category: {e}") from e

    def update_category(
        self,
        category_id: int,
        category: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on an existing category.

        Only non-None arguments are applied. Passing no updatable fields
        is a no-op that returns the current row.

        Args:
            category_id: Primary key of the category to update.
            category: New category name, if changing.
            description: New description, if changing.

        Returns:
            The updated category as a dict, or None if `category_id`
            does not exist.

        Raises:
            DatabaseError: If the new name collides with an existing
                category, or on any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if category is not None:
                    updates.append("category = ?")
                    params.append(category)
                    updated_fields.append('category')

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                    updated_fields.append('description')

                if not updates:
                    logger.debug(f"No fields to update for category {category_id}")
                    return self.get_category_by_id(category_id)

                params.append(category_id)
                query = f"UPDATE categories SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Category {category_id} not found for update")
                    return None

            logger.info(f"Updated category {category_id}: {updated_fields}")
            return self.get_category_by_id(category_id)

        except sqlite3.IntegrityError as e:
            logger.warning(f"Duplicate category name on update: {category}")
            raise DatabaseError(f"Category name already exists: {category}") from e
        except Exception as e:
            logger.error(f"Failed to update category {category_id}: {e}")
            raise DatabaseError(f"Failed to update category: {e}") from e

    def get_category_by_id(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single category by primary key.

        Args:
            category_id: The category's `id` column value.

        Returns:
            The category row as a dict, or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            row = self.br.select_query(
                "SELECT * FROM categories WHERE id = ?",
                params=(category_id,)
            )
            if not row:
                logger.debug(f"Category {category_id} not found")
                return None
            return dict(row)

        except Exception as e:
            logger.error(f"Failed to get category {category_id}: {e}")
            raise DatabaseError(f"Failed to get category: {e}") from e

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Fetch every category, ordered alphabetically by name.

        Returns:
            List of category dicts. Empty list if the table is empty.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM categories ORDER BY category")
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} categories")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all categories: {e}")
            raise DatabaseError(f"Failed to get categories: {e}") from e

    def delete_category(self, category_id: int) -> bool:
        """Delete a category by primary key.

        Refuses to delete if the category has any child subcategories,
        matching the `ON DELETE RESTRICT` constraint on
        `sub_categories.category_id`.

        Args:
            category_id: Primary key of the category to delete.

        Returns:
            True if the category was deleted, False if it did not exist.

        Raises:
            DatabaseError: If the category has associated subcategories,
                or on any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM sub_categories WHERE category_id = ?",
                    (category_id,)
                )
                count = cursor.fetchone()['count']

                if count > 0:
                    logger.warning(
                        f"Cannot delete category {category_id}: "
                        f"has {count} associated sub-categories"
                    )
                    raise DatabaseError(
                        f"Cannot delete category {category_id}: "
                        f"has {count} associated sub-category(ies)"
                    )

                cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))

                if cursor.rowcount == 0:
                    logger.debug(f"Category {category_id} not found for deletion")
                    return False

                logger.info(f"Deleted category {category_id}")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete category {category_id}: {e}")
            raise DatabaseError(f"Failed to delete category: {e}") from e

    # ========== Sub-categories ==========

    def add_sub_category(
        self,
        sub_category: str,
        category_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Insert a new subcategory under the given category.

        Args:
            sub_category: Subcategory name (e.g. "Rent", "Groceries").
            category_id: FK to the parent `categories` row.
            description: Optional human-readable description.

        Returns:
            The `id` of the newly created subcategory.

        Raises:
            DatabaseError: If the (sub_category, category_id) pair
                already exists, the parent category doesn't exist,
                or on any other database failure.
        """
        logger.debug(f"Adding sub-category: {sub_category} under category {category_id}")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sub_categories (sub_category, category_id, description) VALUES (?, ?, ?)",
                    (sub_category, category_id, description)
                )
                sub_category_id = cursor.lastrowid

            logger.info(
                f"Added sub-category {sub_category_id}: {sub_category} "
                f"under category {category_id}"
            )
            return sub_category_id

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate sub-category in category {category_id}: {sub_category}")
                raise DatabaseError(f"Sub-category already exists in this category: {sub_category}") from e
            if "foreign key" in error_msg:
                logger.warning(f"Category {category_id} does not exist")
                raise DatabaseError(f"Category {category_id} does not exist") from e
            logger.error(f"Integrity error adding sub-category: {e}")
            raise DatabaseError(f"Failed to add sub-category: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add sub-category: {e}")
            raise DatabaseError(f"Failed to add sub-category: {e}") from e

    def update_sub_category(
        self,
        sub_category_id: int,
        sub_category: Optional[str] = None,
        category_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on an existing subcategory.

        Can re-parent a subcategory under a different category by passing
        a new `category_id`.

        Args:
            sub_category_id: Primary key of the subcategory to update.
            sub_category: New subcategory name, if changing.
            category_id: New parent category ID, if re-parenting.
            description: New description, if changing.

        Returns:
            The updated subcategory as a dict, or None if
            `sub_category_id` does not exist.

        Raises:
            DatabaseError: If the (sub_category, category_id) pair
                already exists, the target category doesn't exist,
                or on any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if sub_category is not None:
                    updates.append("sub_category = ?")
                    params.append(sub_category)
                    updated_fields.append('sub_category')

                if category_id is not None:
                    updates.append("category_id = ?")
                    params.append(category_id)
                    updated_fields.append('category_id')

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                    updated_fields.append('description')

                if not updates:
                    logger.debug(f"No fields to update for sub-category {sub_category_id}")
                    return self.get_sub_category_by_id(sub_category_id)

                params.append(sub_category_id)
                query = f"UPDATE sub_categories SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Sub-category {sub_category_id} not found for update")
                    return None

            logger.info(f"Updated sub-category {sub_category_id}: {updated_fields}")
            return self.get_sub_category_by_id(sub_category_id)

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate sub-category name on update: {sub_category}")
                raise DatabaseError(f"Sub-category name already exists in this category") from e
            if "foreign key" in error_msg:
                logger.warning(f"Category {category_id} does not exist")
                raise DatabaseError(f"Category {category_id} does not exist") from e
            logger.error(f"Integrity error updating sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to update sub-category: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to update sub-category: {e}") from e

    def get_sub_category_by_id(self, sub_category_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single subcategory by primary key.

        Args:
            sub_category_id: The subcategory's `id` column value.

        Returns:
            The subcategory row as a dict, or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sub_categories WHERE id = ?", (sub_category_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Sub-category {sub_category_id} not found")
                    return None
                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to get sub-category: {e}") from e

    def get_all_sub_categories(self) -> List[Dict[str, Any]]:
        """Fetch every subcategory with its parent category name.

        Joins to `categories` to include `category_name` in each row.
        Results are ordered by category then subcategory name.

        Returns:
            List of subcategory dicts, each including a `category_name`
            field. Empty list if no subcategories exist.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sc.*, c.category as category_name
                    FROM sub_categories sc
                    JOIN categories c ON sc.category_id = c.id
                    ORDER BY c.category, sc.sub_category
                ''')
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} sub-categories")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all sub-categories: {e}")
            raise DatabaseError(f"Failed to get sub-categories: {e}") from e

    def get_sub_categories_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Fetch all subcategories belonging to a given category.

        Args:
            category_id: Parent category to filter by.

        Returns:
            List of subcategory dicts, ordered by name. Empty list if
            the category has no subcategories (or doesn't exist).

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM sub_categories WHERE category_id = ? ORDER BY sub_category",
                    (category_id,)
                )
                rows = cursor.fetchall()

                logger.debug(
                    f"Retrieved {len(rows)} sub-categories for category {category_id}"
                )
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get sub-categories for category {category_id}: {e}")
            raise DatabaseError(f"Failed to get sub-categories: {e}") from e

    def delete_sub_category(self, sub_category_id: int) -> bool:
        """Delete a subcategory by primary key.

        Refuses to delete if the subcategory has any child types,
        matching the `ON DELETE RESTRICT` constraint on
        `types.sub_category_id`.

        Args:
            sub_category_id: Primary key of the subcategory to delete.

        Returns:
            True if deleted, False if the subcategory did not exist.

        Raises:
            DatabaseError: If the subcategory has associated types,
                or on any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM types WHERE sub_category_id = ?",
                    (sub_category_id,)
                )
                count = cursor.fetchone()['count']

                if count > 0:
                    logger.warning(
                        f"Cannot delete sub-category {sub_category_id}: "
                        f"has {count} associated types"
                    )
                    raise DatabaseError(
                        f"Cannot delete sub-category {sub_category_id}: "
                        f"has {count} associated type(s)"
                    )

                cursor.execute("DELETE FROM sub_categories WHERE id = ?", (sub_category_id,))

                if cursor.rowcount == 0:
                    logger.debug(f"Sub-category {sub_category_id} not found for deletion")
                    return False

                logger.info(f"Deleted sub-category {sub_category_id}")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to delete sub-category: {e}") from e

    # ========== Types ==========

    def add_type(
        self,
        type_name: str,
        sub_category_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Insert a new type under the given subcategory.

        Args:
            type_name: Type name (e.g. "Supermarket", "Streaming").
            sub_category_id: FK to the parent `sub_categories` row.
            description: Optional human-readable description.

        Returns:
            The `id` of the newly created type.

        Raises:
            DatabaseError: If the (type, sub_category_id) pair already
                exists, the parent subcategory doesn't exist, or on any
                other database failure.
        """
        logger.debug(f"Adding type: {type_name} under sub-category {sub_category_id}")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO types (type, sub_category_id, description) VALUES (?, ?, ?)",
                    (type_name, sub_category_id, description)
                )
                type_id = cursor.lastrowid

            logger.info(
                f"Added type {type_id}: {type_name} "
                f"under sub-category {sub_category_id}"
            )
            return type_id

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(
                    f"Duplicate type in sub-category {sub_category_id}: {type_name}"
                )
                raise DatabaseError(f"Type already exists in this sub-category: {type_name}") from e
            if "foreign key" in error_msg:
                logger.warning(f"Sub-category {sub_category_id} does not exist")
                raise DatabaseError(f"Sub-category {sub_category_id} does not exist") from e
            logger.error(f"Integrity error adding type: {e}")
            raise DatabaseError(f"Failed to add type: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add type: {e}")
            raise DatabaseError(f"Failed to add type: {e}") from e

    def update_type(
        self,
        type_id: int,
        type_name: Optional[str] = None,
        sub_category_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update one or more fields on an existing type.

        Can re-parent a type under a different subcategory by passing a
        new `sub_category_id`.

        Args:
            type_id: Primary key of the type to update.
            type_name: New type name, if changing.
            sub_category_id: New parent subcategory ID, if re-parenting.
            description: New description, if changing.

        Returns:
            The updated type as a dict, or None if `type_id` does not
            exist.

        Raises:
            DatabaseError: If the (type, sub_category_id) pair already
                exists, the target subcategory doesn't exist, or on any
                other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if type_name is not None:
                    updates.append("type = ?")
                    params.append(type_name)
                    updated_fields.append('type')

                if sub_category_id is not None:
                    updates.append("sub_category_id = ?")
                    params.append(sub_category_id)
                    updated_fields.append('sub_category_id')

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                    updated_fields.append('description')

                if not updates:
                    logger.debug(f"No fields to update for type {type_id}")
                    return self.get_type_by_id(type_id)

                params.append(type_id)
                query = f"UPDATE types SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Type {type_id} not found for update")
                    return None

            logger.info(f"Updated type {type_id}: {updated_fields}")
            return self.get_type_by_id(type_id)

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate type name on update: {type_name}")
                raise DatabaseError(f"Type name already exists in this sub-category") from e
            if "foreign key" in error_msg:
                logger.warning(f"Sub-category {sub_category_id} does not exist")
                raise DatabaseError(f"Sub-category {sub_category_id} does not exist") from e
            logger.error(f"Integrity error updating type {type_id}: {e}")
            raise DatabaseError(f"Failed to update type: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update type {type_id}: {e}")
            raise DatabaseError(f"Failed to update type: {e}") from e

    def get_type_by_id(self, type_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single type by primary key.

        Args:
            type_id: The type's `id` column value.

        Returns:
            The type row as a dict, or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM types WHERE id = ?", (type_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Type {type_id} not found")
                    return None
                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get type {type_id}: {e}")
            raise DatabaseError(f"Failed to get type: {e}") from e

    def get_all_types(self) -> List[Dict[str, Any]]:
        """Fetch every type with full hierarchy context.

        Joins through `sub_categories` and `categories` to include
        `sub_category_name`, `category_id`, and `category_name` in each
        row. Ordered by category → subcategory → type name.

        Returns:
            List of type dicts with hierarchy fields. Empty list if no
            types exist.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*, sc.sub_category as sub_category_name, 
                        c.id as category_id, c.category as category_name
                    FROM types t
                    JOIN sub_categories sc ON t.sub_category_id = sc.id
                    JOIN categories c ON sc.category_id = c.id
                    ORDER BY c.category, sc.sub_category, t.type
                ''')
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} types")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get all types: {e}")
            raise DatabaseError(f"Failed to get types: {e}") from e

    def get_types_by_sub_category(self, sub_category_id: int) -> List[Dict[str, Any]]:
        """Fetch all types belonging to a given subcategory.

        Args:
            sub_category_id: Parent subcategory to filter by.

        Returns:
            List of type dicts, ordered by name. Empty list if the
            subcategory has no types (or doesn't exist).

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM types WHERE sub_category_id = ? ORDER BY type",
                    (sub_category_id,)
                )
                rows = cursor.fetchall()

                logger.debug(
                    f"Retrieved {len(rows)} types for sub-category {sub_category_id}"
                )
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get types for sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to get types: {e}") from e

    def delete_type(self, type_id: int) -> bool:
        """Delete a type by primary key.

        Refuses to delete if the type has any child parties, matching
        the `ON DELETE RESTRICT` constraint on `parties.type_id`.

        Args:
            type_id: Primary key of the type to delete.

        Returns:
            True if deleted, False if the type did not exist.

        Raises:
            DatabaseError: If the type has associated parties, or on
                any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM parties WHERE type_id = ?",
                    (type_id,)
                )
                count = cursor.fetchone()['count']

                if count > 0:
                    logger.warning(
                        f"Cannot delete type {type_id}: "
                        f"has {count} associated parties"
                    )
                    raise DatabaseError(
                        f"Cannot delete type {type_id}: "
                        f"has {count} associated party(ies)"
                    )

                cursor.execute("DELETE FROM types WHERE id = ?", (type_id,))

                if cursor.rowcount == 0:
                    logger.debug(f"Type {type_id} not found for deletion")
                    return False

                logger.info(f"Deleted type {type_id}")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete type {type_id}: {e}")
            raise DatabaseError(f"Failed to delete type: {e}") from e

    # ========== Parties ==========

    def add_party(
        self,
        name: str,
        type_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Insert a new party under the given type.

        Parties are the leaf level of the hierarchy and represent
        transaction counterparties (e.g. "Tesco", "Netflix").

        Args:
            name: Party name as extracted/cleaned from statements.
            type_id: FK to the parent `types` row.
            description: Optional human-readable description.

        Returns:
            The `id` of the newly created party.

        Raises:
            DatabaseError: If the (name, type_id) pair already exists,
                the parent type doesn't exist, or on any other database
                failure.
        """
        logger.debug(f"Adding party: {name} under type {type_id}")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO parties (name, type_id, description) VALUES (?, ?, ?)",
                    (name, type_id, description)
                )
                party_id = cursor.lastrowid

            logger.info(f"Added party {party_id}: {name} under type {type_id}")
            return party_id

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate party in type {type_id}: {name}")
                raise DatabaseError(f"Party already exists in this type: {name}") from e
            if "foreign key" in error_msg:
                logger.warning(f"Type {type_id} does not exist")
                raise DatabaseError(f"Type {type_id} does not exist") from e
            logger.error(f"Integrity error adding party: {e}")
            raise DatabaseError(f"Failed to add party: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add party: {e}")
            raise DatabaseError(f"Failed to add party: {e}") from e

    def add_party_unknown_type(
        self,
        name: str,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Insert a new party under the auto-created "Unknown" hierarchy.

        Ensures the full Unknown → Unknown → Unknown chain
        (category → sub_category → type) exists, creating it if needed,
        then inserts the party. Used during statement import when a
        transaction description can't be matched to a known party.

        Args:
            name: Party name as extracted from the statement.
            description: Optional human-readable description.

        Returns:
            The `id` of the newly created party.

        Raises:
            DatabaseError: If the party already exists under the Unknown
                type, or on any other database failure.
        """
        logger.debug(f"Adding party with unknown type: {name}")

        try:
            type_id = self._ensure_unknown_hierarchy()
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO parties (name, type_id, description) VALUES (?, ?, ?)",
                    (name, type_id, description)
                )
                party_id = cursor.lastrowid

            logger.info(
                f"Added party {party_id}: {name} under unknown type {type_id}"
            )
            return party_id

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate party in unknown type: {name}")
                raise DatabaseError(f"Party already exists in this type: {name}") from e
            if "foreign key" in error_msg:
                logger.error(f"Unknown type {type_id} unexpectedly missing")
                raise DatabaseError(f"Type {type_id} does not exist") from e
            logger.error(f"Integrity error adding party: {e}")
            raise DatabaseError(f"Failed to add party: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add party: {e}")
            raise DatabaseError(f"Failed to add party: {e}") from e

    def bulk_add_parties_unknown_type(self, names: list[str]) -> dict[str, int]:
        """Insert many parties under the Unknown type in one transaction.

        Uses `INSERT OR IGNORE` so pre-existing parties are silently
        skipped, then reads back IDs for everything — new and
        pre-existing alike. Input names are deduplicated internally.

        Designed for statement import, where dozens of new parties may
        appear at once.

        Args:
            names: Party names to insert. Duplicates are ignored.

        Returns:
            Mapping of `{name: party_id}` for every name in the input,
            whether newly inserted or already present.

        Raises:
            DatabaseError: On any database failure.
        """
        if not names:
            return {}

        type_id = self._ensure_unknown_hierarchy()
        # Defensive dedupe — callers shouldn't pass dupes, but don't blow up if they do
        unique_names = list(dict.fromkeys(names))

        logger.info(f"Bulk inserting {len(unique_names)} parties under type {type_id}")

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # executemany keeps it to one round of Python→C marshalling
                cursor.executemany(
                    "INSERT OR IGNORE INTO parties (name, type_id, description) "
                    "VALUES (?, ?, NULL)",
                    [(n, type_id) for n in unique_names],
                )
                inserted = cursor.rowcount  # -1 on some drivers, but useful when it works

                # Read back IDs for everything — new and pre-existing alike.
                # SQLite's param limit is 32,766 (since 3.32.0); 900 is fine.
                # Chunk if you ever expect >30k in one go.
                placeholders = ",".join("?" * len(unique_names))
                cursor.execute(
                    f"SELECT name, id FROM parties "
                    f"WHERE type_id = ? AND name IN ({placeholders})",
                    [type_id, *unique_names],
                )
                result = dict(cursor.fetchall())

            logger.info(
                f"Bulk insert complete: {len(result)} ids returned "
                f"({inserted if inserted >= 0 else '?'} newly inserted)"
            )
            return result

        except Exception as e:
            logger.error(f"Bulk party insert failed: {e}")
            raise DatabaseError(f"Failed to bulk add parties: {e}") from e

    def update_party(
        self,
        party_id: int,
        name: Optional[str] = None,
        type_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a party's name and/or description.

        Does not support changing `type_id` — use `remap_party()` for
        that, since it handles the `UNIQUE(name, type_id)` constraint
        by merging when a conflict exists and re-pointing transactions.

        Args:
            party_id: Primary key of the party to update.
            name: New party name, if changing.
            type_id: Not allowed — raises `ValueError`. Use
                `remap_party()` instead.
            description: New description, if changing.

        Returns:
            The updated party as a dict, or None if `party_id` does not
            exist.

        Raises:
            ValueError: If `type_id` is provided.
            DatabaseError: If the new name conflicts with an existing
                party under the same type, or on any other database
                failure.
        """
        if type_id is not None:
            raise ValueError(
                "Cannot change type_id through update_party(). "
                "Use remap_party() instead, which handles potential "
                "merge conflicts with existing parties."
            )

        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                updates = []
                params = []
                updated_fields = []

                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                    updated_fields.append('name')

                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                    updated_fields.append('description')

                if not updates:
                    logger.debug(f"No fields to update for party {party_id}")
                    return self.get_party_by_id(party_id)

                params.append(party_id)
                query = f"UPDATE parties SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)

                if cursor.rowcount == 0:
                    logger.debug(f"Party {party_id} not found for update")
                    return None

            logger.info(f"Updated party {party_id}: {updated_fields}")
            return self.get_party_by_id(party_id)

        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                logger.warning(f"Duplicate party name on update: {name}")
                raise DatabaseError(
                    f"A party named '{name}' already exists under this type"
                ) from e
            logger.error(f"Integrity error updating party {party_id}: {e}")
            raise DatabaseError(f"Failed to update party: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update party {party_id}: {e}")
            raise DatabaseError(f"Failed to update party: {e}") from e

    def remap_party(self, party_id: int, new_type_id: int) -> dict:
        """Move a party to a different type in the category hierarchy.

        Handles the `UNIQUE(name, type_id)` constraint intelligently:

        - If no party with the same name exists under the target type,
          simply updates `type_id` (a "remap").
        - If a same-named party already exists, merges: re-points all of
          the old party's transactions to the existing party, then
          deletes the old party row (a "merge").

        This is the only method that should be used to change a party's
        `type_id`. See `update_party()` for name/description changes.

        Args:
            party_id: Primary key of the party to move.
            new_type_id: Target type to move the party under.

        Returns:
            Dict describing the outcome:
                - `{'action': 'none', ...}` — party already at target type.
                - `{'action': 'remapped', ...}` — `type_id` updated in place.
                - `{'action': 'merged', ...}` — transactions moved and old
                  party deleted. Includes `transactions_moved` count.

        Raises:
            ValueError: If `party_id` or `new_type_id` does not exist.
            DatabaseError: On any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Get the party we're remapping
                cursor.execute(
                    "SELECT id, name, type_id FROM parties WHERE id = ?",
                    (party_id,)
                )
                party = cursor.fetchone()

                if not party:
                    raise ValueError(f"Party {party_id} not found")

                party_name = party['name']
                old_type_id = party['type_id']

                # No-op check
                if old_type_id == new_type_id:
                    logger.info(
                        f"Party '{party_name}' (id={party_id}) already "
                        f"mapped to type_id={new_type_id}"
                    )
                    return {
                        'action': 'none',
                        'party_id': party_id,
                        'message': 'Party already mapped to this type',
                    }

                # Validate target type exists
                cursor.execute(
                    "SELECT id FROM types WHERE id = ?",
                    (new_type_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Type {new_type_id} not found")

                # Check for UNIQUE(name, type_id) conflict
                cursor.execute(
                    "SELECT id FROM parties "
                    "WHERE name = ? AND type_id = ? AND id != ?",
                    (party_name, new_type_id, party_id)
                )
                existing = cursor.fetchone()

                if existing:
                    return self._merge_parties(
                        cursor, party_id, existing['id'],
                        party_name, new_type_id
                    )
                else:
                    return self._remap_party_type(
                        cursor, party_id, party_name,
                        old_type_id, new_type_id
                    )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to remap party {party_id}: {e}")
            raise DatabaseError(f"Failed to remap party: {e}") from e

    def _merge_parties(
        self,
        cursor,
        old_party_id: int,
        target_party_id: int,
        party_name: str,
        new_type_id: int,
    ) -> dict:
        """Merge a party into an existing same-named party under the target type.

        Re-points all transactions from `old_party_id` to
        `target_party_id`, then deletes the old party row. Called by
        `remap_party()` when a naming conflict is detected.

        Args:
            cursor: Active database cursor (within a transaction).
            old_party_id: Party being merged away (will be deleted).
            target_party_id: Party that absorbs the transactions.
            party_name: Shared name (for logging).
            new_type_id: Target type ID (for logging).

        Returns:
            Dict with `action='merged'`, both party IDs, and
            `transactions_moved` count.
        """

        # Re-point transactions
        cursor.execute(
            "UPDATE transactions SET party_id = ? WHERE party_id = ?",
            (target_party_id, old_party_id)
        )
        transactions_moved = cursor.rowcount

        # Re-point aliases if you have an aliases table
        # cursor.execute(
        #     "UPDATE party_aliases SET party_id = ? WHERE party_id = ?",
        #     (target_party_id, old_party_id)
        # )

        # Delete the now-orphaned party
        cursor.execute(
            "DELETE FROM parties WHERE id = ?",
            (old_party_id,)
        )

        logger.info(
            f"Merged party '{party_name}' (id={old_party_id}) into "
            f"existing party (id={target_party_id}) under "
            f"type_id={new_type_id}. "
            f"Moved {transactions_moved} transactions."
        )

        return {
            'action': 'merged',
            'old_party_id': old_party_id,
            'new_party_id': target_party_id,
            'type_id': new_type_id,
            'transactions_moved': transactions_moved,
        }

    def _remap_party_type(
        self,
        cursor,
        party_id: int,
        party_name: str,
        old_type_id: int,
        new_type_id: int,
    ) -> dict:
        """Update a party's `type_id` when no naming conflict exists.

        Called by `remap_party()` for the simple case.

        Args:
            cursor: Active database cursor (within a transaction).
            party_id: Party to update.
            party_name: Current party name (for logging).
            old_type_id: Previous type ID (for logging).
            new_type_id: New type ID to set.

        Returns:
            Dict with `action='remapped'`, party ID, old/new type IDs,
            and `transactions_affected` count.
        """

        cursor.execute(
            "UPDATE parties SET type_id = ? WHERE id = ?",
            (new_type_id, party_id)
        )

        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE party_id = ?",
            (party_id,)
        )
        tx_count = cursor.fetchone()['count']

        logger.info(
            f"Remapped party '{party_name}' (id={party_id}) "
            f"from type_id={old_type_id} to type_id={new_type_id}. "
            f"{tx_count} transactions affected."
        )

        return {
            'action': 'remapped',
            'party_id': party_id,
            'old_type_id': old_type_id,
            'new_type_id': new_type_id,
            'transactions_affected': tx_count,
        }

    def get_party_by_id(self, party_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single party by primary key.

        Args:
            party_id: The party's `id` column value.

        Returns:
            The party row as a dict, or None if no match.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM parties WHERE id = ?", (party_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Party {party_id} not found")
                    return None
                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get party {party_id}: {e}")
            raise DatabaseError(f"Failed to get party: {e}") from e

    def get_all_parties_with_transaction_counts(self) -> List[Dict[str, Any]]:
        """Fetch every party with full hierarchy context and transaction counts.

        Joins through the full hierarchy (`types` → `sub_categories` →
        `categories`) and LEFT JOINs `transactions` to produce a
        `transaction_count` for each party. Ordered by party name.

        Returns:
            List of party dicts, each including `type_name`,
            `sub_category_id`, `sub_category_name`, `category_id`,
            `category_name`, and `transaction_count`. Empty list if no
            parties exist.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.*, 
                        t.type as type_name,
                        sc.id as sub_category_id,
                        sc.sub_category as sub_category_name,
                        c.id as category_id,
                        c.category as category_name,
                        COUNT(tr.id) as transaction_count
                    FROM parties p
                    JOIN types t ON p.type_id = t.id
                    JOIN sub_categories sc ON t.sub_category_id = sc.id
                    JOIN categories c ON sc.category_id = c.id
                    LEFT JOIN transactions tr ON tr.party_id = p.id
                    GROUP BY p.id
                    ORDER BY p.name
                ''')
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} parties with transaction counts")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get parties with counts: {e}")
            raise DatabaseError(f"Failed to get parties: {e}") from e

    def get_parties_by_type(self, type_id: int) -> List[Dict[str, Any]]:
        """Fetch all parties belonging to a given type.

        Args:
            type_id: Parent type to filter by.

        Returns:
            List of party dicts, ordered by name. Empty list if the
            type has no parties (or doesn't exist).

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM parties WHERE type_id = ? ORDER BY name",
                    (type_id,)
                )
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} parties for type {type_id}")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get parties for type {type_id}: {e}")
            raise DatabaseError(f"Failed to get parties: {e}") from e

    def delete_party(self, party_id: int) -> bool:
        """Delete a party by primary key.

        Refuses to delete if the party has any linked transactions,
        matching the `ON DELETE RESTRICT` constraint on
        `transactions.party_id`.

        Args:
            party_id: Primary key of the party to delete.

        Returns:
            True if deleted, False if the party did not exist.

        Raises:
            DatabaseError: If the party has associated transactions,
                or on any other database failure.
        """
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count FROM transactions WHERE party_id = ?",
                    (party_id,)
                )
                count = cursor.fetchone()['count']

                if count > 0:
                    logger.warning(
                        f"Cannot delete party {party_id}: "
                        f"has {count} associated transactions"
                    )
                    raise DatabaseError(
                        f"Cannot delete party {party_id}: "
                        f"has {count} associated transaction(s)"
                    )

                cursor.execute("DELETE FROM parties WHERE id = ?", (party_id,))

                if cursor.rowcount == 0:
                    logger.debug(f"Party {party_id} not found for deletion")
                    return False

                logger.info(f"Deleted party {party_id}")
                return True

        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete party {party_id}: {e}")
            raise DatabaseError(f"Failed to delete party: {e}") from e

    def get_transactions_by_party(self, party_id: int) -> List[Dict[str, Any]]:
        """Fetch all transactions for a given party, with account info.

        Joins to `accounts` to include `account_name` on each row.
        Ordered by transaction date descending (most recent first).

        Args:
            party_id: Party to filter transactions by.

        Returns:
            List of transaction dicts, each including `account_name`.
            Empty list if the party has no transactions.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*, a.account_name
                    FROM transactions t
                    LEFT JOIN accounts a ON t.account_id = a.id
                    WHERE t.party_id = ?
                    ORDER BY t.transaction_date DESC
                ''', (party_id,))
                rows = cursor.fetchall()

                logger.debug(f"Retrieved {len(rows)} transactions for party {party_id}")
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get transactions for party {party_id}: {e}")
            raise DatabaseError(f"Failed to get transactions: {e}") from e

    # ========== Hierarchy ==========

    def get_party_hierarchy(self, party_id: int) -> Optional[Dict[str, Any]]:
        """Fetch the full four-level hierarchy path for a party.

        Returns a single flat dict with IDs and names for each level:
        party → type → sub_category → category.

        Args:
            party_id: The party to look up.

        Returns:
            Dict with `party_id`, `party_name`, `type_id`, `type_name`,
            `sub_category_id`, `sub_category_name`, `category_id`, and
            `category_name`. None if the party doesn't exist.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        p.id as party_id,
                        p.name as party_name,
                        t.id as type_id,
                        t.type as type_name,
                        sc.id as sub_category_id,
                        sc.sub_category as sub_category_name,
                        c.id as category_id,
                        c.category as category_name
                    FROM parties p
                    JOIN types t ON p.type_id = t.id
                    JOIN sub_categories sc ON t.sub_category_id = sc.id
                    JOIN categories c ON sc.category_id = c.id
                    WHERE p.id = ?
                ''', (party_id,))

                row = cursor.fetchone()
                if not row:
                    logger.debug(f"No hierarchy found for party {party_id}")
                    return None
                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get hierarchy for party {party_id}: {e}")
            raise DatabaseError(f"Failed to get party hierarchy: {e}") from e

    def get_all_party_aliases(self) -> Dict[str, int]:
        """Build a mapping of known description strings to party IDs.

        Combines two sources, both upper-cased for case-insensitive
        matching:
            1. `cleaned_description` values from `transactions` — what
               the categorizer saw before.
            2. `name` values from `parties` — canonical party names.

        Transaction descriptions take priority (added first via
        `setdefault`). The result is used by the auto-categorizer to
        match incoming transactions to known parties.

        Returns:
            Dict of `{UPPERCASE_ALIAS: party_id}`. Empty dict if no
            parties or transactions exist.

        Raises:
            DatabaseError: On query failure.
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT DISTINCT 
                        t.cleaned_description as alias,
                        t.party_id
                    FROM transactions t
                    ORDER BY t.cleaned_description
                ''')
                alias_data = cursor.fetchall()

                cursor.execute('''
                    SELECT DISTINCT 
                        p.name as alias,
                        p.id as party_id
                    FROM parties p
                    ORDER BY p.name
                ''')
                party_data = cursor.fetchall()

            alias_mapping = {}
            for row in alias_data:
                if row['alias']:
                    alias_mapping.setdefault(row['alias'].upper(), row['party_id'])
            for row in party_data:
                if row['alias']:
                    alias_mapping.setdefault(row['alias'].upper(), row['party_id'])

            logger.debug(
                f"Built alias mapping: {len(alias_mapping)} aliases "
                f"({len(alias_data)} from transactions, "
                f"{len(party_data)} from parties)"
            )
            return alias_mapping

        except Exception as e:
            logger.error(f"Failed to get party aliases: {e}")
            raise DatabaseError(f"Failed to get party aliases: {e}") from e

    def _ensure_unknown_hierarchy(self) -> int:
        """Ensure the "Unknown" category/subcategory/type chain exists.

        Creates any missing levels of the hierarchy:
            Unknown (category) → Unknown (sub_category) → Unknown (type)

        The resulting type ID is cached on the instance so subsequent
        calls skip the database entirely.

        Returns:
            The `id` of the "Unknown" type row.
        """
        if self._unknown_type_id is not None:
            logger.debug(
                f"Unknown hierarchy type_id resolved from cache: "
                f"{self._unknown_type_id}"
            )
            return self._unknown_type_id

        logger.debug("Ensuring 'Unknown' hierarchy exists")

        unknown_category = self.br.select_query(
            "SELECT id FROM categories WHERE category = ?",
            ("Unknown",)
        )
        if unknown_category:
            category_id = unknown_category['id']
        else:
            category_id = self.add_category("Unknown", "Automatically created unknown category")
            logger.info(f"Created 'Unknown' category: {category_id}")

        unknown_sub_category = self.br.select_query(
            "SELECT id FROM sub_categories WHERE sub_category = ? AND category_id = ?",
            ("Unknown", category_id)
        )
        if unknown_sub_category:
            sub_category_id = unknown_sub_category['id']
        else:
            sub_category_id = self.add_sub_category(
                "Unknown", category_id, "Automatically created unknown sub-category"
            )
            logger.info(f"Created 'Unknown' sub-category: {sub_category_id}")

        unknown_type = self.br.select_query(
            "SELECT id FROM types WHERE type = ? AND sub_category_id = ?",
            ("Unknown", sub_category_id)
        )
        if unknown_type:
            type_id = unknown_type['id']
        else:
            type_id = self.add_type(
                "Unknown", sub_category_id, "Automatically created unknown type"
            )
            logger.info(f"Created 'Unknown' type: {type_id}")

        self._unknown_type_id = type_id
        logger.debug(f"Unknown hierarchy type_id cached: {type_id}")
        return self._unknown_type_id

    def prime_unknown_type_cache(self) -> int:
        """Eagerly resolve and cache the "Unknown" type ID.

        Call before batch operations that may create many new parties
        (e.g. statement import) so the hierarchy lookup and potential
        creation happens once, up front, rather than on the first
        `add_party_unknown_type()` call.

        Returns:
            The cached "Unknown" type `id`.
        """
        return self._ensure_unknown_hierarchy()