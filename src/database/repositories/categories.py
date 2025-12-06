from typing import Optional, Dict, List, Any, Union, Tuple
import logging
import sqlite3

from src.database.connection import get_manager, DatabaseError
from src.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class CategoryRepository:
    """Repository for category hierarchy CRUD operations"""
    
    def __init__(self):
        self.db = get_manager()
        self.br = BaseRepository()
    
    # ========== Categories ==========

    def add_category(self, category: str, description: Optional[str] = None) -> Union[int, None]:
        """Add a new category"""
        try:
            category_id = self.br.insert_query(
                "INSERT INTO categories (category, description) VALUES (?, ?)",
                (category, description)
            )
            return category_id
        except sqlite3.IntegrityError as e:
            if "unique" in str(e).lower():
                raise DatabaseError(f"Category already exists: {category}") from e
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
        """Update a category"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if category is not None:
                    updates.append("category = ?")
                    params.append(category)
                
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                
                if not updates:
                    return self.get_category_by_id(category_id)
                
                params.append(category_id)
                query = f"UPDATE categories SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Category {category_id} not found for update")
                    return None
            
            return self.get_category_by_id(category_id)
        except sqlite3.IntegrityError as e:
            raise DatabaseError(f"Category name already exists: {category}") from e
        except Exception as e:
            logger.error(f"Failed to update category {category_id}: {e}")
            raise DatabaseError(f"Failed to update category: {e}") from e

    def get_category_by_id(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Get a category by ID"""
        try:
            row = self.br.select_query(
                "SELECT * FROM categories WHERE id = ?",
                params=str(category_id)
                )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get category {category_id}: {e}")
            raise DatabaseError(f"Failed to get category: {e}") from e
    
    # ========== Sub-categories ==========
    
    def add_sub_category(
        self,
        sub_category: str,
        category_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Add a new sub-category"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sub_categories (sub_category, category_id, description) VALUES (?, ?, ?)",
                    (sub_category, category_id, description)
                )
                sub_category_id = cursor.lastrowid
                logger.info(f"Added sub-category {sub_category_id}: {sub_category}")
                return sub_category_id
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Sub-category already exists in this category: {sub_category}") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Category {category_id} does not exist") from e
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
        """Update a sub-category"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if sub_category is not None:
                    updates.append("sub_category = ?")
                    params.append(sub_category)
                
                if category_id is not None:
                    updates.append("category_id = ?")
                    params.append(category_id)
                
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                
                if not updates:
                    return self.get_sub_category_by_id(sub_category_id)
                
                params.append(sub_category_id)
                query = f"UPDATE sub_categories SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Sub-category {sub_category_id} not found for update")
                    return None
            
            return self.get_sub_category_by_id(sub_category_id)
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Sub-category name already exists in this category") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Category {category_id} does not exist") from e
            raise DatabaseError(f"Failed to update sub-category: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to update sub-category: {e}") from e
    
    def get_sub_category_by_id(self, sub_category_id: int) -> Optional[Dict[str, Any]]:
        """Get a sub-category by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM sub_categories WHERE id = ?", (sub_category_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get sub-category {sub_category_id}: {e}")
            raise DatabaseError(f"Failed to get sub-category: {e}") from e
    
    # ========== Types ==========
    
    def add_type(
        self,
        type_name: str,
        sub_category_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Add a new type"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO types (type, sub_category_id, description) VALUES (?, ?, ?)",
                    (type_name, sub_category_id, description)
                )
                type_id = cursor.lastrowid
                logger.info(f"Added type {type_id}: {type_name}")
                return type_id
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Type already exists in this sub-category: {type_name}") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Sub-category {sub_category_id} does not exist") from e
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
        """Update a type"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if type_name is not None:
                    updates.append("type = ?")
                    params.append(type_name)
                
                if sub_category_id is not None:
                    updates.append("sub_category_id = ?")
                    params.append(sub_category_id)
                
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                
                if not updates:
                    return self.get_type_by_id(type_id)
                
                params.append(type_id)
                query = f"UPDATE types SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Type {type_id} not found for update")
                    return None
            
            return self.get_type_by_id(type_id)
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Type name already exists in this sub-category") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Sub-category {sub_category_id} does not exist") from e
            raise DatabaseError(f"Failed to update type: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update type {type_id}: {e}")
            raise DatabaseError(f"Failed to update type: {e}") from e
    
    def get_type_by_id(self, type_id: int) -> Optional[Dict[str, Any]]:
        """Get a type by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM types WHERE id = ?", (type_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get type {type_id}: {e}")
            raise DatabaseError(f"Failed to get type: {e}") from e
    
    # ========== Parties ==========
    
    def add_party(
        self,
        name: str,
        type_id: int,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Add a new party"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO parties (name, type_id, description) VALUES (?, ?, ?)",
                    (name, type_id, description)
                )
                party_id = cursor.lastrowid
                logger.info(f"Added party {party_id}: {name}")
                return party_id
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Party already exists in this type: {name}") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Type {type_id} does not exist") from e
            raise DatabaseError(f"Failed to add party: {e}") from e
        except Exception as e:
            logger.error(f"Failed to add party: {e}")
            raise DatabaseError(f"Failed to add party: {e}") from e

    def add_party_unknown_type(
        self,
        name: str,
        description: Optional[str] = None
    ) -> Union[int, None]:
        """Add a new party"""
        try:
            type_id = self.create_unknown_category()
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO parties (name, type_id, description) VALUES (?, ?, ?)",
                    (name, type_id, description)
                )
                party_id = cursor.lastrowid
                logger.info(f"Added party {party_id}: {name}")
                return party_id
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Party already exists in this type: {name}") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Type {type_id} does not exist") from e
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
        """Update a party"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                
                if type_id is not None:
                    updates.append("type_id = ?")
                    params.append(type_id)
                
                if description is not None:
                    updates.append("description = ?")
                    params.append(description)
                
                if not updates:
                    return self.get_party_by_id(party_id)
                
                params.append(party_id)
                query = f"UPDATE parties SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.warning(f"Party {party_id} not found for update")
                    return None
            
            return self.get_party_by_id(party_id)
        except sqlite3.IntegrityError as e:
            error_msg = str(e).lower()
            if "unique" in error_msg:
                raise DatabaseError(f"Party name already exists in this type") from e
            if "foreign key" in error_msg:
                raise DatabaseError(f"Type {type_id} does not exist") from e
            raise DatabaseError(f"Failed to update party: {e}") from e
        except Exception as e:
            logger.error(f"Failed to update party {party_id}: {e}")
            raise DatabaseError(f"Failed to update party: {e}") from e
    
    def get_party_by_id(self, party_id: int) -> Optional[Dict[str, Any]]:
        """Get a party by ID"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM parties WHERE id = ?", (party_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get party {party_id}: {e}")
            raise DatabaseError(f"Failed to get party: {e}") from e
    
    # ========== Hierarchy ==========
    
    def get_party_hierarchy(self, party_id: int) -> Optional[Dict[str, Any]]:
        """Get the complete hierarchy for a party"""
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
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get party hierarchy for {party_id}: {e}")
            raise DatabaseError(f"Failed to get party hierarchy: {e}") from e
        
    def get_all_parties(self) -> Dict[str, int]:
        """
        Get all unique cleaned_description values from transactions 
        along with their party_id and canonical name from the parties table
        
        Returns:
            List of dictionaries with keys:
            - cleaned_description: The cleaned transaction description
            - party_id: The associated party ID (can be None)
            - canonical_name: The party name from parties table (can be None)
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

            # Process the results
            all_names = []
            if alias_data:
                all_names.extend(alias_data)
            if party_data:
                all_names.extend(party_data)

            alias_mapping = {}
            
            for row in all_names:
                if row['alias'] not in alias_mapping:
                    alias_mapping[row['alias'].upper()] = row['party_id']
            return alias_mapping

        except Exception as e:
            logger.error(f"Failed to get all parties: {e}")
            raise DatabaseError(f"Failed to get all parties: {e}") from e
        
    def create_unknown_category(self) -> int:
        """Create or get the 'Unknown' category, sub-category, and type."""
        unknown_category = self.br.select_query(
            "SELECT id FROM categories WHERE category = ?",
            ("Unknown",)
        )
        if unknown_category:
            category_id = unknown_category['id']
        else:
            category_id = self.add_category("Unknown", "Automatically created unknown category")
        
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
        
        return type_id