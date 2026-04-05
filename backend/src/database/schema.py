"""
Database schema definition and creation for SQLite.

Defines every table, index, and trigger in the application database via
the `SchemaManager` class. All DDL uses `CREATE ... IF NOT EXISTS`, so
`init_db()` is safe to call on every startup.

Called automatically by `connection.init_app()` when `create_tables=True`.

Table dependency order (foreign keys flow downward):

    receipts
    categories
      └─ subcategories
           └─ types
                └─ parties
    uploads
      └─ upload_data
    accounts
    transactions  ← references accounts, uploads, parties, receipts
"""

from src.database.connection import ConnectionManager
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class SchemaManager:
    """Creates and manages the application's database schema.

    Encapsulates all table definitions in one place so the full schema
    is visible at a glance. Each private `_create_*` method is
    responsible for one table and its associated indexes / triggers.

    Attributes:
        TABLES: Ordered list of table names. Creation order respects
            foreign key constraints — referenced tables come first.
        db: The `ConnectionManager` used to obtain connections.
    """

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
        """Initialize with a connection manager.

        Args:
            connection_manager: The `ConnectionManager` instance to use
                for obtaining database connections.
        """
        self.db = connection_manager

    def init_db(self):
        """Create all application tables, indexes, and triggers.

        Calls each `_create_*` method in foreign-key-safe order. Every
        statement uses `IF NOT EXISTS`, so this is idempotent and safe to
        run against an already-initialized database.

        Raises:
            Exception: Propagates any database error after logging it.
        """
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
        """Create the `categories` table and name index.

        Columns:
            id: Auto-incrementing primary key.
            category: Unique category name (e.g. "Housing", "Food").
            description: Optional human-readable description.
            created_at: Row creation timestamp.
        """
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
        """Create the `sub_categories` table and indexes.

        Each subcategory belongs to exactly one category. The combination
        of (sub_category, category_id) is unique.

        Columns:
            id: Auto-incrementing primary key.
            sub_category: Subcategory name (e.g. "Rent", "Groceries").
            description: Optional human-readable description.
            category_id: FK → `categories.id`. Restricts delete.
            created_at: Row creation timestamp.
        """
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
        """Create the `types` table and indexes.

        Types sit below subcategories in the category hierarchy:
        category → sub_category → type → party.

        Columns:
            id: Auto-incrementing primary key.
            type: Type name (e.g. "Supermarket", "Streaming").
            description: Optional human-readable description.
            sub_category_id: FK → `sub_categories.id`. Restricts delete.
            created_at: Row creation timestamp.
        """
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
        """Create the `parties` table and indexes.

        Parties are the leaf level of the category hierarchy and represent
        the counterparty on a transaction (e.g. "Tesco", "Netflix").

        Columns:
            id: Auto-incrementing primary key.
            name: Party name as extracted/cleaned from statements.
            description: Optional human-readable description.
            type_id: FK → `types.id`. Restricts delete.
            created_at: Row creation timestamp.
        """
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
        """Create the `receipts` table, indexes, and update trigger.

        Stores metadata for uploaded receipt images. Receipts can
        optionally be linked to a transaction via `transactions.receipt_id`.

        Columns:
            id: Auto-incrementing primary key.
            original_filename: Name of the file as uploaded by the user.
            stored_filename: Unique on-disk filename (deduplicated).
            file_path: Full path to the stored file.
            vendor: Extracted vendor/merchant name.
            date: Extracted receipt date.
            amount: Extracted total (must be >= 0).
            confidence: Extraction confidence score (0–3).
            selected_method: Which extraction method produced the result.
            raw_text: Full OCR text output.
            metadata: JSON string with additional extraction data.
            created_at: Row creation timestamp.
            updated_at: Auto-updated on row modification via trigger.

        Indexes: vendor, date, created_at.
        """
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
        """Create the `uploads` table and indexes.

        Tracks metadata about uploaded statement files (CSV, Excel, etc.).
        The actual row data is stored in `upload_data`.

        Columns:
            id: Auto-incrementing primary key.
            original_filename: Name as uploaded by the user.
            filename: Stored/deduplicated filename.
            file_type: MIME type or extension (e.g. "csv", "xlsx").
            row_count: Number of data rows in the file.
            column_count: Number of columns in the file.
            columns: JSON-encoded list of column names.
            upload_date: When the file was uploaded.
            created_at: Row creation timestamp.

        Indexes: filename, file_type, upload_date.
        """
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
        """Create the `upload_data` table and indexes.

        Stores the raw row data from each uploaded file. Each row is
        kept as a JSON string so the schema is file-format-agnostic.

        Columns:
            id: Auto-incrementing primary key.
            upload_id: FK → `uploads.id`. Cascades on delete.
            row_index: Zero-based row position within the source file.
            row_data: JSON-encoded contents of the row.
            created_at: Row creation timestamp.

        The (upload_id, row_index) pair is unique.

        Indexes: upload_id, row_index.
        """
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
        """Create the `transactions` table and indexes.

        The central table — every imported bank/card transaction ends up
        here. Links to the category hierarchy via `party_id` and
        optionally to a receipt image via `receipt_id`.

        Columns:
            id: Auto-incrementing primary key.
            transaction_date: Date the transaction occurred.
            amount: Transaction value. Negative for debits, positive for credits.
            description: Raw description from the bank statement.
            cleaned_description: Normalised description after parsing.
            is_credit: 1 for income/credit, 0 for expense/debit.
            is_kids: 1 if flagged as a child-related expense.
            is_one_off: 1 if flagged as non-recurring.
            account_id: FK → `accounts.id`. Restricts delete.
            upload_id: FK → `uploads.id`. Restricts delete.
            party_id: FK → `parties.id`. Restricts delete.
            receipt_id: FK → `receipts.id`. Set to NULL on receipt delete.
            created_at: Row creation timestamp.

        Indexes: transaction_date, account_id, party_id, upload_id,
            is_credit, receipt_id.
        """
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
        """Create the `accounts` table and indexes.

        Represents a bank or card account that transactions are imported
        from. The `statement_format` column (added by migration) links
        to the statement parser registry.

        Columns:
            id: Auto-incrementing primary key.
            account_name: User-facing account label.
            account_type: Account kind (e.g. "current", "credit").
            created_at: Row creation timestamp.

        Note:
            The `statement_format` column is added separately by
            `migrations.migrate()` rather than in this DDL, for
            backwards compatibility with existing databases.

        Indexes: account_name, account_type.
        """
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
    """Create all tables using the provided connection manager.

    Convenience wrapper around `SchemaManager` for callers that don't
    need to hold onto the manager instance.

    Args:
        connection_manager: The `ConnectionManager` to use for database
            access.
    """
    schema_manager = SchemaManager(connection_manager)
    schema_manager.init_db()