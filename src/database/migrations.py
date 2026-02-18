import sqlite3


def migrate(db_path: str):
    """One-time migration — run manually or via a startup hook."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if old column exists and new one doesn't
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(accounts)")]

    if "statement_format" not in columns:
        # SQLite doesn't support DROP COLUMN before 3.35,
        # so just add the new column alongside
        cursor.execute(
            "ALTER TABLE accounts ADD COLUMN statement_format TEXT"
        )
        # Optionally copy from account_type if any values are salvageable
        # cursor.execute("UPDATE accounts SET statement_format = account_type")
        conn.commit()
        print("Migration complete: added 'statement_format' column")
    else:
        print("Migration already applied")

    conn.close()