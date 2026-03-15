from src.database.connection import ConnectionManager
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class SchemaManager:
   """Manages database schema creation and migrations."""

   # Table creation order matters due to foreign key constraints
   TABLES = [
       'receipts',
       'categories',
       'subcategories',
       'types',
       'parties',
       'uploads',
       'upload_data',
       'accounts',
       'transactions',
   ]

   def __init__(self, connection_manager: ConnectionManager):
       self.db = connection_manager

   def init_db(self):
       """Initialize database with all required tables."""
       logger.info(f"Initializing database schema ({len(self.TABLES)} tables)")

       try:
           self._create_receipts_table()
           self._create_categories_table()
           self._create_subcategories_table()
           self._create_types_table()
           self._create_parties_table()
           self._create_uploads_table()
           self._create_upload_data_table()
           self._create_accounts_table()
           self._create_transactions_table()

           logger.info("Database schema initialized successfully")
       except Exception as e:
           logger.error(f"Schema initialization failed: {e}")
           raise

   def _create_categories_table(self):
       """Create categories table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS categories (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   category TEXT NOT NULL UNIQUE,
                   description TEXT,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_categories_category 
               ON categories(category)
           ''')

           conn.commit()
           logger.debug("Table ready: categories")

   def _create_subcategories_table(self):
       """Create sub-categories table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS sub_categories (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   sub_category TEXT NOT NULL,
                   description TEXT,
                   category_id INTEGER NOT NULL,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   FOREIGN KEY (category_id) REFERENCES categories(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   UNIQUE (sub_category, category_id)
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_sub_categories_sub_category 
               ON sub_categories(sub_category)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_sub_categories_category_id 
               ON sub_categories(category_id)
           ''')

           conn.commit()
           logger.debug("Table ready: sub_categories")

   def _create_types_table(self):
       """Create types table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS types (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   type TEXT NOT NULL,
                   description TEXT,
                   sub_category_id INTEGER NOT NULL,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   FOREIGN KEY (sub_category_id) REFERENCES sub_categories(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   UNIQUE (type, sub_category_id)
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_types_type 
               ON types(type)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_types_sub_category_id 
               ON types(sub_category_id)
           ''')

           conn.commit()
           logger.debug("Table ready: types")

   def _create_parties_table(self):
       """Create parties table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS parties (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL,
                   description TEXT,
                   type_id INTEGER NOT NULL,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   FOREIGN KEY (type_id) REFERENCES types(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   UNIQUE (name, type_id)
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_parties_name 
               ON parties(name)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_parties_type_id 
               ON parties(type_id)
           ''')

           conn.commit()
           logger.debug("Table ready: parties")

   def _create_receipts_table(self):
       """Create receipts table with proper schema."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS receipts (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   original_filename TEXT NOT NULL,
                   stored_filename TEXT NOT NULL,
                   file_path TEXT NOT NULL,
                   vendor TEXT,
                   date DATE,
                   amount REAL CHECK(amount >= 0),
                   confidence INTEGER DEFAULT 0 CHECK(confidence >= 0 AND confidence <= 3),
                   selected_method TEXT,
                   raw_text TEXT,
                   metadata TEXT,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   updated_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   UNIQUE (stored_filename)
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_receipts_vendor 
               ON receipts(vendor)
           ''')
           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_receipts_date 
               ON receipts(date)
           ''')
           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_receipts_created 
               ON receipts(created_at)
           ''')

           cursor.execute('''
               CREATE TRIGGER IF NOT EXISTS update_receipts_timestamp 
               AFTER UPDATE ON receipts
               BEGIN
                   UPDATE receipts SET updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                   WHERE id = NEW.id;
               END
           ''')

           conn.commit()
           logger.debug("Table ready: receipts")

   def _create_uploads_table(self):
       """Create uploads table for tracking file uploads."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS uploads (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   original_filename TEXT NOT NULL,
                   filename TEXT NOT NULL,
                   file_type TEXT NOT NULL,
                   row_count INTEGER NOT NULL DEFAULT 0,
                   column_count INTEGER NOT NULL DEFAULT 0,
                   columns TEXT,
                   upload_date TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_uploads_filename 
               ON uploads(filename)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_uploads_file_type 
               ON uploads(file_type)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_uploads_upload_date 
               ON uploads(upload_date)
           ''')

           conn.commit()
           logger.debug("Table ready: uploads")

   def _create_upload_data_table(self):
       """Create upload_data table for storing imported row data."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS upload_data (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   upload_id INTEGER NOT NULL,
                   row_index INTEGER NOT NULL,
                   row_data TEXT NOT NULL,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   FOREIGN KEY (upload_id) REFERENCES uploads(id)
                       ON DELETE CASCADE ON UPDATE CASCADE,
                   UNIQUE (upload_id, row_index)
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_upload_data_upload_id 
               ON upload_data(upload_id)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_upload_data_row_index 
               ON upload_data(row_index)
           ''')

           conn.commit()
           logger.debug("Table ready: upload_data")

   def _create_transactions_table(self):
       """Create transactions table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS transactions (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   transaction_date DATE NOT NULL,
                   amount REAL NOT NULL,
                   description TEXT NOT NULL,
                   cleaned_description TEXT,
                   is_credit INTEGER NOT NULL CHECK(is_credit IN (0, 1)),
                   is_kids INTEGER NOT NULL DEFAULT 0 CHECK(is_kids IN (0, 1)),
                   is_one_off INTEGER NOT NULL DEFAULT 0 CHECK(is_one_off IN (0, 1)),
                   account_id INTEGER,
                   upload_id INTEGER NOT NULL,
                   party_id INTEGER NOT NULL,
                   receipt_id INTEGER,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
                   FOREIGN KEY (account_id) REFERENCES accounts(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   FOREIGN KEY (upload_id) REFERENCES uploads(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   FOREIGN KEY (party_id) REFERENCES parties(id)
                       ON DELETE RESTRICT ON UPDATE CASCADE,
                   FOREIGN KEY (receipt_id) REFERENCES receipts(id)
                       ON DELETE SET NULL ON UPDATE CASCADE
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_date 
               ON transactions(transaction_date)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_account_id 
               ON transactions(account_id)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_party_id 
               ON transactions(party_id)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_upload_id 
               ON transactions(upload_id)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_is_credit 
               ON transactions(is_credit)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_transactions_receipt_id 
               ON transactions(receipt_id)
           ''')

           conn.commit()
           logger.debug("Table ready: transactions")

   def _create_accounts_table(self):
       """Create accounts table."""
       with self.db.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS accounts (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   account_name TEXT NOT NULL,
                   account_type TEXT NOT NULL,
                   created_at TIMESTAMP DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
               )
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_accounts_account_name 
               ON accounts(account_name)
           ''')

           cursor.execute('''
               CREATE INDEX IF NOT EXISTS idx_accounts_account_type 
               ON accounts(account_type)
           ''')

           conn.commit()
           logger.debug("Table ready: accounts")


def initialize_schema(connection_manager: ConnectionManager):
   """Convenience function to initialize schema."""
   schema_manager = SchemaManager(connection_manager)
   schema_manager.init_db()