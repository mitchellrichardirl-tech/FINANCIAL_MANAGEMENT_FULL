from typing import Optional, Dict, List, Any, Union
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.base import BaseRepository
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class CategoryRepository:
    """Repository for category hierarchy CRUD operations."""

    def __init__(self):
        self.db = get_manager()
        self.br = BaseRepository()
        self._unknown_type_id = None

    # ========== Categories ==========

    def add_category(self, category: str, description: Optional[str] = None) -> Union[int, None]:
        """Add a new category."""
        logger.debug(f"Adding category: {category}")

        try:
            category_id = self.br.insert_query(
                "INSERT INTO categories (category, description) VALUES (?, ?)",
                (category, description)
            )
            logger.info(f"Added category {category_id}: {category}")
            return category_id

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
        """Update a category."""
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
        """Get a category by ID."""
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
        """Get all categories."""
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
        """
        Delete a category by ID.
        
        Returns True if deleted, False if not found.
        Raises DatabaseError if category has associated sub-categories.
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
        """Add a new sub-category."""
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
        """Update a sub-category."""
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
        """Get a sub-category by ID."""
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
        """Get all sub-categories with their category info."""
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
        """Get all sub-categories for a specific category."""
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
        """
        Delete a sub-category by ID.
        
        Returns True if deleted, False if not found.
        Raises DatabaseError if sub-category has associated types.
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
        """Add a new type."""
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
        """Update a type."""
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
        """Get a type by ID."""
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
        """Get all types with their hierarchy info."""
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
        """Get all types for a specific sub-category."""
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
        """
        Delete a type by ID.
        
        Returns True if deleted, False if not found.
        Raises DatabaseError if type has associated parties.
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
        """Add a new party."""
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
        """Add a new party under the 'Unknown' type hierarchy."""
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

    def update_party(
        self,
        party_id: int,
        name: Optional[str] = None,
        type_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update a party's name and/or description.

        For changing a party's type_id, use remap_party() instead — it
        handles the UNIQUE(name, type_id) constraint by merging when a
        conflict exists, and logs the transaction impact.

        Args:
            party_id: The party to update
            name: New name (optional)
            type_id: Rejected — raises ValueError, use remap_party()
            description: New description (optional)

        Returns:
            Updated party dict, or None if not found
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
        """
        Remap a party to a new type in the category hierarchy.

        If a party with the same name already exists under the target type,
        merges: re-points all transactions to the existing party and deletes
        the old one. Otherwise, simply updates the type_id.

        This is the only method that should change a party's type_id.

        Args:
            party_id: The party to remap
            new_type_id: The target type_id

        Returns:
            Dict describing what happened (remapped, merged, or no-op)
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
        """Merge old party into an existing party under the target type."""

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
        """Simple remap — no naming conflict."""

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
        """Get a party by ID."""
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
        """Get all parties with their transaction counts and hierarchy info."""
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
        """Get all parties for a specific type."""
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
        """
        Delete a party by ID.
        
        Returns True if deleted, False if not found.
        Raises DatabaseError if party has associated transactions.
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
        """Get all transactions for a specific party."""
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
        """Get the complete hierarchy for a party."""
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
        """
        Get mapping of all party aliases (from transaction descriptions
        and party names) to their party IDs.
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
        """Ensure 'Unknown' hierarchy exists and return its type_id.

        Result is cached on the instance — the Unknown hierarchy is static
        data that never changes at runtime, so querying it once per
        repository lifetime is sufficient.
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
        """Eagerly resolve and cache the Unknown type_id.

        Call this before any batch operation that may add multiple new
        parties, so the hierarchy lookup only happens once regardless of
        how many parties are created.

        Returns the cached type_id for convenience.
        """
        return self._ensure_unknown_hierarchy()