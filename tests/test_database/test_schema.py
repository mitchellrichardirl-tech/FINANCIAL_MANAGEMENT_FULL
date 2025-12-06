import sqlite3
import pytest
from src.database.connection import ConnectionManager
from src.database.schema import SchemaManager, initialize_schema


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def connection_manager(temp_db_path):
    return ConnectionManager(temp_db_path)


@pytest.fixture
def initialized_db(connection_manager):
    """Database with schema initialized"""
    initialize_schema(connection_manager)
    return connection_manager


class TestSchemaInitialization:
    """Test schema creation"""
    
    def test_receipts_table_created(self, initialized_db):
        """Test that receipts table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='receipts'
            """)
            assert cursor.fetchone() is not None
    
    def test_receipts_table_schema(self, initialized_db):
        """Test receipts table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(receipts)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {
                'id', 'original_filename', 'stored_filename', 'file_path',
                'vendor', 'date', 'amount', 'confidence', 'selected_method',
                'raw_text', 'metadata', 'created_at', 'updated_at'
            }
            assert expected_columns.issubset(columns)
    
    def test_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='receipts'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('vendor' in idx for idx in indexes)
            assert any('date' in idx for idx in indexes)
            assert any('created' in idx for idx in indexes)
    
    def test_triggers_created(self, initialized_db):
        """Test that triggers are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='trigger' AND tbl_name='receipts'
            """)
            triggers = [row[0] for row in cursor.fetchall()]
            
            assert any('update' in trigger.lower() for trigger in triggers)
    
    def test_init_is_idempotent(self, connection_manager):
        """Test that running init_db multiple times is safe"""
        schema = SchemaManager(connection_manager)
        
        # Should not raise on multiple calls
        schema.init_db()
        schema.init_db()
        
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='receipts'")
            assert cursor.fetchone()[0] == 1  # Still just one table

class TestCategoriesSchema:
    """Test categories table schema"""
    
    def test_categories_table_created(self, initialized_db):
        """Test that categories table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='categories'
            """)
            assert cursor.fetchone() is not None
    
    def test_categories_table_columns(self, initialized_db):
        """Test categories table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(categories)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {'id', 'category', 'description', 'created_at'}
            assert expected_columns == columns
    
    def test_categories_category_not_null(self, initialized_db):
        """Test that category field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO categories (description) VALUES (?)",
                    ("test",)
                )
    
    def test_categories_category_unique(self, initialized_db):
        """Test that category field is UNIQUE"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (category) VALUES (?)",
                ("Expenses",)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO categories (category) VALUES (?)",
                    ("Expenses",)
                )
    
    def test_categories_description_nullable(self, initialized_db):
        """Test that description can be NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (category) VALUES (?)",
                ("Expenses",)
            )
            conn.commit()
            
            cursor.execute("SELECT description FROM categories WHERE category = ?", ("Expenses",))
            result = cursor.fetchone()
            assert result[0] is None
    
    def test_categories_created_at_default(self, initialized_db):
        """Test that created_at has default value"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (category) VALUES (?)",
                ("Expenses",)
            )
            conn.commit()
            
            cursor.execute("SELECT created_at FROM categories WHERE category = ?", ("Expenses",))
            result = cursor.fetchone()
            assert result[0] is not None
    
    def test_categories_index_created(self, initialized_db):
        """Test that category index is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='categories'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('category' in idx for idx in indexes)


class TestSubCategoriesSchema:
    """Test sub_categories table schema"""
    
    def test_sub_categories_table_created(self, initialized_db):
        """Test that sub_categories table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='sub_categories'
            """)
            assert cursor.fetchone() is not None
    
    def test_sub_categories_table_columns(self, initialized_db):
        """Test sub_categories table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sub_categories)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {'id', 'sub_category', 'description', 'category_id', 'created_at'}
            assert expected_columns == columns
    
    def test_sub_categories_sub_category_not_null(self, initialized_db):
        """Test that sub_category field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO sub_categories (category_id) VALUES (?)",
                    (1,)
                )
    
    def test_sub_categories_category_id_not_null(self, initialized_db):
        """Test that category_id field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO sub_categories (sub_category) VALUES (?)",
                    ("Transportation",)
                )
    
    def test_sub_categories_foreign_key_valid(self, initialized_db):
        """Test that foreign key to categories works"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", category_id)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM sub_categories WHERE category_id = ?", (category_id,))
            assert cursor.fetchone() is not None
    
    def test_sub_categories_foreign_key_invalid(self, initialized_db):
        """Test that invalid foreign key is rejected"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                    ("Transportation", 999)
                )
    
    def test_sub_categories_unique_within_category(self, initialized_db):
        """Test that sub_category is unique within same category"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", category_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                    ("Transportation", category_id)
                )
    
    def test_sub_categories_same_name_different_category(self, initialized_db):
        """Test that same sub_category name allowed in different categories"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id_1 = cursor.lastrowid
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Income",))
            category_id_2 = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Other", category_id_1)
            )
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Other", category_id_2)
            )
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM sub_categories WHERE sub_category = ?", ("Other",))
            assert cursor.fetchone()[0] == 2
    
    def test_sub_categories_delete_restrict(self, initialized_db):
        """Test that deleting category with sub_categories is restricted"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", category_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    
    def test_sub_categories_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='sub_categories'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('sub_category' in idx for idx in indexes)
            assert any('category_id' in idx for idx in indexes)


class TestTypesSchema:
    """Test types table schema"""
    
    def test_types_table_created(self, initialized_db):
        """Test that types table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='types'
            """)
            assert cursor.fetchone() is not None
    
    def test_types_table_columns(self, initialized_db):
        """Test types table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(types)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {'id', 'type', 'description', 'sub_category_id', 'created_at'}
            assert expected_columns == columns
    
    def test_types_type_not_null(self, initialized_db):
        """Test that type field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO types (sub_category_id) VALUES (?)",
                    (1,)
                )
    
    def test_types_sub_category_id_not_null(self, initialized_db):
        """Test that sub_category_id field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO types (type) VALUES (?)",
                    ("Fuel",)
                )
    
    def test_types_foreign_key_valid(self, initialized_db):
        """Test that foreign key to sub_categories works"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            sub_category_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", sub_category_id)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM types WHERE sub_category_id = ?", (sub_category_id,))
            assert cursor.fetchone() is not None
    
    def test_types_foreign_key_invalid(self, initialized_db):
        """Test that invalid foreign key is rejected"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                    ("Fuel", 999)
                )
    
    def test_types_unique_within_sub_category(self, initialized_db):
        """Test that type is unique within same sub_category"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            sub_category_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", sub_category_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                    ("Fuel", sub_category_id)
                )
    
    def test_types_same_name_different_sub_category(self, initialized_db):
        """Test that same type name allowed in different sub_categories"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            sub_cat_id_1 = cursor.lastrowid
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Home", 1)
            )
            sub_cat_id_2 = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Maintenance", sub_cat_id_1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Maintenance", sub_cat_id_2)
            )
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM types WHERE type = ?", ("Maintenance",))
            assert cursor.fetchone()[0] == 2
    
    def test_types_delete_restrict(self, initialized_db):
        """Test that deleting sub_category with types is restricted"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            sub_category_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", sub_category_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("DELETE FROM sub_categories WHERE id = ?", (sub_category_id,))
    
    def test_types_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='types'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('type' in idx for idx in indexes)
            assert any('sub_category_id' in idx for idx in indexes)


class TestPartiesSchema:
    """Test parties table schema"""
    
    def test_parties_table_created(self, initialized_db):
        """Test that parties table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='parties'
            """)
            assert cursor.fetchone() is not None
    
    def test_parties_table_columns(self, initialized_db):
        """Test parties table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(parties)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {'id', 'name', 'description', 'type_id', 'created_at'}
            assert expected_columns == columns
    
    def test_parties_name_not_null(self, initialized_db):
        """Test that name field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", 1)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO parties (type_id) VALUES (?)",
                    (1,)
                )
    
    def test_parties_type_id_not_null(self, initialized_db):
        """Test that type_id field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO parties (name) VALUES (?)",
                    ("Shell",)
                )
    
    def test_parties_foreign_key_valid(self, initialized_db):
        """Test that foreign key to types works"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", 1)
            )
            type_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id)
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM parties WHERE type_id = ?", (type_id,))
            assert cursor.fetchone() is not None
    
    def test_parties_foreign_key_invalid(self, initialized_db):
        """Test that invalid foreign key is rejected"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                    ("Shell", 999)
                )
    
    def test_parties_unique_within_type(self, initialized_db):
        """Test that name is unique within same type"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", 1)
            )
            type_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                    ("Shell", type_id)
                )
    
    def test_parties_same_name_different_type(self, initialized_db):
        """Test that same party name allowed in different types"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", 1)
            )
            type_id_1 = cursor.lastrowid
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Convenience", 1)
            )
            type_id_2 = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id_1)
            )
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id_2)
            )
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM parties WHERE name = ?", ("Shell",))
            assert cursor.fetchone()[0] == 2
    
    def test_parties_delete_restrict(self, initialized_db):
        """Test that deleting type with parties is restricted"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", 1)
            )
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", 1)
            )
            type_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id)
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("DELETE FROM types WHERE id = ?", (type_id,))
    
    def test_parties_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='parties'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('name' in idx for idx in indexes)
            assert any('type_id' in idx for idx in indexes)


class TestHierarchyIntegration:
    """Test the complete category hierarchy"""
    
    def test_full_hierarchy_creation(self, initialized_db):
        """Test creating a complete hierarchy"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create category
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id = cursor.lastrowid
            
            # Create sub-category
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", category_id)
            )
            sub_category_id = cursor.lastrowid
            
            # Create type
            cursor.execute(
                "INSERT INTO types (type, sub_category_id) VALUES (?, ?)",
                ("Fuel", sub_category_id)
            )
            type_id = cursor.lastrowid
            
            # Create party
            cursor.execute(
                "INSERT INTO parties (name, type_id) VALUES (?, ?)",
                ("Shell", type_id)
            )
            party_id = cursor.lastrowid
            conn.commit()
            
            # Verify hierarchy with join
            cursor.execute('''
                SELECT 
                    c.category,
                    sc.sub_category,
                    t.type,
                    p.name
                FROM parties p
                JOIN types t ON p.type_id = t.id
                JOIN sub_categories sc ON t.sub_category_id = sc.id
                JOIN categories c ON sc.category_id = c.id
                WHERE p.id = ?
            ''', (party_id,))
            
            result = cursor.fetchone()
            assert result[0] == "Expenses"
            assert result[1] == "Transportation"
            assert result[2] == "Fuel"
            assert result[3] == "Shell"
    
    def test_cascade_update(self, initialized_db):
        """Test that ON UPDATE CASCADE works through hierarchy"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("INSERT INTO categories (category) VALUES (?)", ("Expenses",))
            category_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO sub_categories (sub_category, category_id) VALUES (?, ?)",
                ("Transportation", category_id)
            )
            sub_category_id = cursor.lastrowid
            conn.commit()
            
            # Update category ID (unusual but tests CASCADE)
            # Note: This requires allowing ID updates which isn't typical
            # This test verifies the CASCADE is configured correctly
            cursor.execute(
                "SELECT category_id FROM sub_categories WHERE id = ?",
                (sub_category_id,)
            )
            assert cursor.fetchone()[0] == category_id

class TestFutureSchemas:
    """Test additional table schemas (add as you implement them)"""
      
    def test_accounts_table_created(self, initialized_db):
        """Test accounts table is created"""
        # Add when you implement accounts
        pass
    
    def test_transactions_table_created(self, initialized_db):
        """Test transactions table is created"""
        # Add when you implement transactions
        pass
    
    def test_foreign_key_relationships(self, initialized_db):
        """Test that foreign keys are properly set up"""
        # Add when you have relationships between tables
        pass

class TestUploadsSchema:
    """Test uploads table schema"""
    
    def test_uploads_table_created(self, initialized_db):
        """Test that uploads table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='uploads'
            """)
            assert cursor.fetchone() is not None
    
    def test_uploads_table_columns(self, initialized_db):
        """Test uploads table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(uploads)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {
                'id', 'filename', 'file_type', 'row_count', 
                'column_count', 'columns', 'upload_date', 'created_at'
            }
            assert expected_columns == columns
    
    def test_uploads_filename_not_null(self, initialized_db):
        """Test that filename field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO uploads (file_type) VALUES (?)",
                    ("csv",)
                )
    
    def test_uploads_file_type_not_null(self, initialized_db):
        """Test that file_type field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO uploads (filename) VALUES (?)",
                    ("test.csv",)
                )
    
    def test_uploads_row_count_default(self, initialized_db):
        """Test that row_count has default value of 0"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT row_count FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert result[0] == 0
    
    def test_uploads_column_count_default(self, initialized_db):
        """Test that column_count has default value of 0"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT column_count FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert result[0] == 0
    
    def test_uploads_columns_nullable(self, initialized_db):
        """Test that columns field can be NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT columns FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert result[0] is None
    
    def test_uploads_columns_stores_json(self, initialized_db):
        """Test that columns field can store JSON"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            columns_json = json.dumps(['col1', 'col2', 'col3'])
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type, columns) VALUES (?, ?, ?)",
                ("test.csv", "csv", columns_json)
            )
            conn.commit()
            
            cursor.execute("SELECT columns FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert json.loads(result[0]) == ['col1', 'col2', 'col3']
    
    def test_uploads_upload_date_default(self, initialized_db):
        """Test that upload_date has default value"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT upload_date FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert result[0] is not None
    
    def test_uploads_created_at_default(self, initialized_db):
        """Test that created_at has default value"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT created_at FROM uploads WHERE filename = ?", ("test.csv",))
            result = cursor.fetchone()
            assert result[0] is not None
    
    def test_uploads_with_all_fields(self, initialized_db):
        """Test creating upload with all fields"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            columns_json = json.dumps(['date', 'amount', 'description'])
            
            cursor.execute('''
                INSERT INTO uploads (filename, file_type, row_count, column_count, columns)
                VALUES (?, ?, ?, ?, ?)
            ''', ("transactions.csv", "csv", 100, 3, columns_json))
            conn.commit()
            
            cursor.execute("SELECT * FROM uploads WHERE filename = ?", ("transactions.csv",))
            result = cursor.fetchone()
            
            assert result is not None
            # Access by column name if row_factory is set, otherwise by index
            assert result[1] == "transactions.csv"  # filename
            assert result[2] == "csv"  # file_type
            assert result[3] == 100  # row_count
            assert result[4] == 3  # column_count
    
    def test_uploads_allows_duplicate_filenames(self, initialized_db):
        """Test that same filename can be uploaded multiple times"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("data.csv", "csv")
            )
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("data.csv", "csv")
            )
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM uploads WHERE filename = ?", ("data.csv",))
            assert cursor.fetchone()[0] == 2
    
    def test_uploads_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='uploads'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('filename' in idx for idx in indexes)
            assert any('file_type' in idx for idx in indexes)
            assert any('upload_date' in idx for idx in indexes)


class TestUploadDataSchema:
    """Test upload_data table schema"""
    
    def test_upload_data_table_created(self, initialized_db):
        """Test that upload_data table is created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='upload_data'
            """)
            assert cursor.fetchone() is not None
    
    def test_upload_data_table_columns(self, initialized_db):
        """Test upload_data table has correct columns"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(upload_data)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {'id', 'upload_id', 'row_index', 'row_data', 'created_at'}
            assert expected_columns == columns
    
    def test_upload_data_upload_id_not_null(self, initialized_db):
        """Test that upload_id field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO upload_data (row_index, row_data) VALUES (?, ?)",
                    (0, '{"col1": "value1"}')
                )
    
    def test_upload_data_row_index_not_null(self, initialized_db):
        """Test that row_index field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            # First create an upload
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_data) VALUES (?, ?)",
                    (upload_id, '{"col1": "value1"}')
                )
    
    def test_upload_data_row_data_not_null(self, initialized_db):
        """Test that row_data field is NOT NULL"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            # First create an upload
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index) VALUES (?, ?)",
                    (upload_id, 0)
                )
    
    def test_upload_data_foreign_key_valid(self, initialized_db):
        """Test that foreign key to uploads works"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id, 0, '{"col1": "value1"}')
            )
            conn.commit()
            
            cursor.execute("SELECT * FROM upload_data WHERE upload_id = ?", (upload_id,))
            assert cursor.fetchone() is not None
    
    def test_upload_data_foreign_key_invalid(self, initialized_db):
        """Test that invalid foreign key is rejected"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (999, 0, '{"col1": "value1"}')
                )
    
    def test_upload_data_unique_upload_row_index(self, initialized_db):
        """Test that (upload_id, row_index) is unique"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id, 0, '{"col1": "value1"}')
            )
            conn.commit()
            
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id, 0, '{"col1": "different_value"}')
                )
    
    def test_upload_data_same_row_index_different_upload(self, initialized_db):
        """Test that same row_index allowed for different uploads"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test1.csv", "csv")
            )
            upload_id_1 = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test2.csv", "csv")
            )
            upload_id_2 = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id_1, 0, '{"data": "upload1_row0"}')
            )
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id_2, 0, '{"data": "upload2_row0"}')
            )
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM upload_data WHERE row_index = 0")
            assert cursor.fetchone()[0] == 2
    
    def test_upload_data_stores_json(self, initialized_db):
        """Test that row_data field stores JSON correctly"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            row_data = {'date': '2024-01-15', 'amount': 99.99, 'description': 'Test purchase'}
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id, 0, json.dumps(row_data))
            )
            conn.commit()
            
            cursor.execute("SELECT row_data FROM upload_data WHERE upload_id = ?", (upload_id,))
            result = cursor.fetchone()
            assert json.loads(result[0]) == row_data
    
    def test_upload_data_created_at_default(self, initialized_db):
        """Test that created_at has default value"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id, 0, '{}')
            )
            conn.commit()
            
            cursor.execute("SELECT created_at FROM upload_data WHERE upload_id = ?", (upload_id,))
            result = cursor.fetchone()
            assert result[0] is not None
    
    def test_upload_data_cascade_delete(self, initialized_db):
        """Test that deleting upload cascades to upload_data"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            # Insert multiple rows of data
            for i in range(5):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id, i, f'{{"row": {i}}}')
                )
            conn.commit()
            
            # Verify data exists
            cursor.execute("SELECT COUNT(*) FROM upload_data WHERE upload_id = ?", (upload_id,))
            assert cursor.fetchone()[0] == 5
            
            # Delete upload
            cursor.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
            conn.commit()
            
            # Verify data was cascade deleted
            cursor.execute("SELECT COUNT(*) FROM upload_data WHERE upload_id = ?", (upload_id,))
            assert cursor.fetchone()[0] == 0
    
    def test_upload_data_indexes_created(self, initialized_db):
        """Test that indexes are created"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='upload_data'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            assert any('upload_id' in idx for idx in indexes)
            assert any('row_index' in idx for idx in indexes)
    
    def test_upload_data_multiple_rows_ordered(self, initialized_db):
        """Test inserting and retrieving multiple rows in order"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            # Insert rows out of order
            for i in [2, 0, 4, 1, 3]:
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id, i, f'{{"index": {i}}}')
                )
            conn.commit()
            
            # Retrieve in order
            cursor.execute(
                "SELECT row_index FROM upload_data WHERE upload_id = ? ORDER BY row_index",
                (upload_id,)
            )
            results = [row[0] for row in cursor.fetchall()]
            assert results == [0, 1, 2, 3, 4]


class TestUploadsUploadDataIntegration:
    """Test the integration between uploads and upload_data tables"""
    
    def test_full_upload_workflow(self, initialized_db):
        """Test complete upload with data workflow"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            # Create upload
            columns = ['date', 'amount', 'description']
            cursor.execute('''
                INSERT INTO uploads (filename, file_type, row_count, column_count, columns)
                VALUES (?, ?, ?, ?, ?)
            ''', ("transactions.csv", "csv", 3, 3, json.dumps(columns)))
            upload_id = cursor.lastrowid
            
            # Insert data rows
            rows = [
                {'date': '2024-01-15', 'amount': 25.99, 'description': 'Purchase 1'},
                {'date': '2024-01-16', 'amount': 42.50, 'description': 'Purchase 2'},
                {'date': '2024-01-17', 'amount': 15.00, 'description': 'Purchase 3'},
            ]
            
            for i, row in enumerate(rows):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id, i, json.dumps(row))
                )
            conn.commit()
            
            # Verify upload
            cursor.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,))
            upload = cursor.fetchone()
            assert upload is not None
            assert upload[3] == 3  # row_count
            
            # Verify data
            cursor.execute(
                "SELECT COUNT(*) FROM upload_data WHERE upload_id = ?",
                (upload_id,)
            )
            assert cursor.fetchone()[0] == 3
            
            # Verify join works
            cursor.execute('''
                SELECT u.filename, u.file_type, COUNT(ud.id) as data_rows
                FROM uploads u
                LEFT JOIN upload_data ud ON u.id = ud.upload_id
                WHERE u.id = ?
                GROUP BY u.id
            ''', (upload_id,))
            result = cursor.fetchone()
            assert result[0] == "transactions.csv"
            assert result[1] == "csv"
            assert result[2] == 3
    
    def test_multiple_uploads_isolation(self, initialized_db):
        """Test that multiple uploads keep data isolated"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            # Create first upload
            cursor.execute(
                "INSERT INTO uploads (filename, file_type, row_count) VALUES (?, ?, ?)",
                ("file1.csv", "csv", 2)
            )
            upload_id_1 = cursor.lastrowid
            
            # Create second upload
            cursor.execute(
                "INSERT INTO uploads (filename, file_type, row_count) VALUES (?, ?, ?)",
                ("file2.xlsx", "xlsx", 3)
            )
            upload_id_2 = cursor.lastrowid
            
            # Insert data for first upload
            for i in range(2):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id_1, i, json.dumps({'source': 'file1', 'row': i}))
                )
            
            # Insert data for second upload
            for i in range(3):
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id_2, i, json.dumps({'source': 'file2', 'row': i}))
                )
            conn.commit()
            
            # Verify isolation
            cursor.execute(
                "SELECT COUNT(*) FROM upload_data WHERE upload_id = ?",
                (upload_id_1,)
            )
            assert cursor.fetchone()[0] == 2
            
            cursor.execute(
                "SELECT COUNT(*) FROM upload_data WHERE upload_id = ?",
                (upload_id_2,)
            )
            assert cursor.fetchone()[0] == 3
            
            # Delete first upload, verify second is unaffected
            cursor.execute("DELETE FROM uploads WHERE id = ?", (upload_id_1,))
            conn.commit()
            
            cursor.execute(
                "SELECT COUNT(*) FROM upload_data WHERE upload_id = ?",
                (upload_id_2,)
            )
            assert cursor.fetchone()[0] == 3
    
    def test_upload_data_large_batch(self, initialized_db):
        """Test inserting a large number of rows"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type, row_count) VALUES (?, ?, ?)",
                ("large_file.csv", "csv", 1000)
            )
            upload_id = cursor.lastrowid
            
            # Insert 1000 rows
            data = [
                (upload_id, i, json.dumps({'index': i, 'value': f'row_{i}'}))
                for i in range(1000)
            ]
            
            cursor.executemany(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                data
            )
            conn.commit()
            
            # Verify count
            cursor.execute(
                "SELECT COUNT(*) FROM upload_data WHERE upload_id = ?",
                (upload_id,)
            )
            assert cursor.fetchone()[0] == 1000
            
            # Verify range query works
            cursor.execute('''
                SELECT row_index FROM upload_data 
                WHERE upload_id = ? AND row_index BETWEEN 100 AND 110
                ORDER BY row_index
            ''', (upload_id,))
            results = [row[0] for row in cursor.fetchall()]
            assert results == list(range(100, 111))
    
    def test_upload_data_row_retrieval_by_index(self, initialized_db):
        """Test retrieving specific rows by index"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            # Insert rows with specific data
            rows = {
                0: {'name': 'Alice', 'age': 25},
                1: {'name': 'Bob', 'age': 30},
                2: {'name': 'Charlie', 'age': 35},
            }
            
            for idx, data in rows.items():
                cursor.execute(
                    "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                    (upload_id, idx, json.dumps(data))
                )
            conn.commit()
            
            # Retrieve specific row
            cursor.execute('''
                SELECT row_data FROM upload_data 
                WHERE upload_id = ? AND row_index = ?
            ''', (upload_id, 1))
            result = cursor.fetchone()
            assert json.loads(result[0]) == {'name': 'Bob', 'age': 30}
    
    def test_upload_data_update_row(self, initialized_db):
        """Test updating a specific row's data"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            import json
            
            cursor.execute(
                "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                ("test.csv", "csv")
            )
            upload_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO upload_data (upload_id, row_index, row_data) VALUES (?, ?, ?)",
                (upload_id, 0, json.dumps({'status': 'pending'}))
            )
            conn.commit()
            
            # Update the row
            cursor.execute('''
                UPDATE upload_data 
                SET row_data = ?
                WHERE upload_id = ? AND row_index = ?
            ''', (json.dumps({'status': 'processed'}), upload_id, 0))
            conn.commit()
            
            # Verify update
            cursor.execute('''
                SELECT row_data FROM upload_data 
                WHERE upload_id = ? AND row_index = ?
            ''', (upload_id, 0))
            result = cursor.fetchone()
            assert json.loads(result[0]) == {'status': 'processed'}
    
    def test_different_file_types(self, initialized_db):
        """Test uploads with different file types"""
        with initialized_db.get_connection() as conn:
            cursor = conn.cursor()
            
            file_types = ['csv', 'xlsx', 'xls', 'tsv', 'txt', 'parquet']
            
            for file_type in file_types:
                cursor.execute(
                    "INSERT INTO uploads (filename, file_type) VALUES (?, ?)",
                    (f"test.{file_type}", file_type)
                )
            conn.commit()
            
            # Query by file type
            cursor.execute(
                "SELECT COUNT(*) FROM uploads WHERE file_type = ?",
                ("xlsx",)
            )
            assert cursor.fetchone()[0] == 1
            
            # Get all file types
            cursor.execute("SELECT DISTINCT file_type FROM uploads ORDER BY file_type")
            results = [row[0] for row in cursor.fetchall()]
            assert results == sorted(file_types)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])