"""
Migration tests for receipts.status / receipts.confirmed_at / receipt_links.
Strategy: build a fully-migrated DB, strip the new schema back out to
simulate a legacy database, seed legacy data, then run migrate() and
assert on the outcome.
"""

import sqlite3

import pytest
from src.database import migrations
from src.database.connection import ConnectionManager
from src.database.migrations import MIGRATIONS, migrate
from src.database.schema import initialize_schema

NEW_MIGRATION_NAMES = {
    "receipts.status",
    "receipts.confirmed_at",
    "receipt_links",
    "receipts.backfill_status_and_links",
}

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _user_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _index_of_first_new_migration():
    names = [m.name for m in MIGRATIONS]
    idx = [i for i, n in enumerate(names) if n in NEW_MIGRATION_NAMES]
    assert idx, "New receipt migrations not registered in MIGRATIONS"
    assert idx == list(range(idx[0], idx[0] + len(idx))), "Receipt migrations must be contiguous"
    return idx[0]


def _seed_legacy_hierarchy(conn):
    conn.execute("INSERT INTO categories (category) VALUES ('Cat')")
    conn.execute(
        "INSERT INTO sub_categories (sub_category, category_id) VALUES ('Sub', 1)"
    )
    conn.execute("INSERT INTO types (type, sub_category_id) VALUES ('Type', 1)")
    conn.execute("INSERT INTO parties (name, type_id) VALUES ('Party', 1)")
    conn.execute("INSERT INTO uploads (filename) VALUES ('legacy.csv')")


def _seed_legacy_receipt(conn, n, vendor="Vendor"):
    cur = conn.execute(
        """INSERT INTO receipts (original_filename, stored_filename, file_path,
                                 vendor, date, amount, confidence)
           VALUES (?, ?, ?, ?, '2024-01-15', 10.0, 2)""",
        (f"r{n}.jpg", f"stored_r{n}.jpg", f"/tmp/r{n}.jpg", vendor),
    )
    return cur.lastrowid


def _seed_legacy_transaction(conn, receipt_id=None, deleted=False):
    cur = conn.execute(
        """INSERT INTO transactions (transaction_date, amount, description,
                                     is_credit, is_kids, is_one_off,
                                     upload_id, party_id, receipt_id, deleted_at)
           VALUES ('2024-01-15', -10.0, 'legacy', 0, 0, 0, 1, 1, ?, ?)""",
        (receipt_id, "2024-02-01 00:00:00.000" if deleted else None),
    )
    return cur.lastrowid


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def base_schema_db(tmp_path):
    """Base schema only — no migrations applied."""
    db_path = tmp_path / "test.db"
    manager = ConnectionManager(db_path)
    initialize_schema(manager)
    return db_path


@pytest.fixture
def fresh_db(base_schema_db):
    """Base schema + every migration."""
    migrate(str(base_schema_db))
    return base_schema_db


@pytest.fixture
def legacy_db(base_schema_db, monkeypatch):
    """Database at the version immediately before the receipt-link migrations."""
    first_new = _index_of_first_new_migration()
    monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS[:first_new])
    migrate(str(base_schema_db))
    monkeypatch.undo()
    conn = sqlite3.connect(base_schema_db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    assert _user_version(conn) == first_new
    assert "status" not in _columns(conn, "receipts")
    assert "receipt_links" not in _tables(conn)
    yield base_schema_db, conn
    conn.close()


# --------------------------------------------------------------------------- #
# Fresh database
# --------------------------------------------------------------------------- #


class TestFreshDatabase:
    def test_receipts_has_new_columns(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        cols = _columns(conn, "receipts")
        assert {"status", "confirmed_at"} <= cols

    def test_receipt_links_table_exists(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        assert "receipt_links" in _tables(conn)
        assert {
            "id",
            "receipt_id",
            "transaction_id",
            "linked_at",
            "link_source",
        } <= _columns(conn, "receipt_links")

    def test_user_version_stamped_to_latest(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        assert _user_version(conn) == len(MIGRATIONS)

    def test_status_default_is_pending(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        conn.execute(
            "INSERT INTO receipts (original_filename, stored_filename, file_path) "
            "VALUES ('a.jpg', 'a.jpg', '/tmp/a.jpg')"
        )
        status = conn.execute("SELECT status FROM receipts").fetchone()[0]
        assert status == "pending"

    def test_status_check_constraint(self, fresh_db):
        conn = sqlite3.connect(fresh_db)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO receipts (original_filename, stored_filename, file_path, status) "
                "VALUES ('a.jpg', 'a.jpg', '/tmp/a.jpg', 'bogus')"
            )

    def test_migrate_is_idempotent(self, fresh_db):
        migrate(str(fresh_db))
        migrate(str(fresh_db))
        conn = sqlite3.connect(fresh_db)
        assert _user_version(conn) == len(MIGRATIONS)


# --------------------------------------------------------------------------- #
# receipt_links constraints
# --------------------------------------------------------------------------- #


class TestReceiptLinksConstraints:
    @pytest.fixture
    def seeded(self, fresh_db):
        conn = sqlite3.connect(fresh_db, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _seed_legacy_hierarchy(conn)
        r1 = _seed_legacy_receipt(conn, 1)
        r2 = _seed_legacy_receipt(conn, 2)
        t1 = _seed_legacy_transaction(conn)
        t2 = _seed_legacy_transaction(conn)
        yield conn, (r1, r2), (t1, t2)
        conn.close()

    def test_one_link_per_receipt(self, seeded):
        conn, (r1, _), (t1, t2) = seeded
        conn.execute(
            "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
            (r1, t1),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
                (r1, t2),
            )

    def test_one_link_per_transaction(self, seeded):
        conn, (r1, r2), (t1, _) = seeded
        conn.execute(
            "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
            (r1, t1),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
                (r2, t1),
            )

    def test_link_source_defaults_to_manual(self, seeded):
        conn, (r1, _), (t1, _) = seeded
        conn.execute(
            "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
            (r1, t1),
        )
        row = conn.execute(
            "SELECT link_source, linked_at FROM receipt_links"
        ).fetchone()
        assert row["link_source"] == "manual"
        assert row["linked_at"] is not None

    def test_deleting_receipt_cascades_link(self, seeded):
        conn, (r1, _), (t1, _) = seeded
        conn.execute(
            "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
            (r1, t1),
        )
        conn.execute("DELETE FROM receipts WHERE id = ?", (r1,))
        assert conn.execute("SELECT COUNT(*) FROM receipt_links").fetchone()[0] == 0

    def test_deleting_transaction_cascades_link(self, seeded):
        conn, (r1, _), (t1, _) = seeded
        conn.execute(
            "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (?, ?)",
            (r1, t1),
        )
        conn.execute("DELETE FROM transactions WHERE id = ?", (t1,))
        assert conn.execute("SELECT COUNT(*) FROM receipt_links").fetchone()[0] == 0

    def test_unknown_receipt_rejected(self, seeded):
        conn, _, (t1, _) = seeded
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO receipt_links (receipt_id, transaction_id) VALUES (9999, ?)",
                (t1,),
            )


# --------------------------------------------------------------------------- #
# Legacy database upgrade + backfill
# --------------------------------------------------------------------------- #


class TestLegacyUpgrade:
    def test_adds_columns_and_table(self, legacy_db):
        db_path, conn = legacy_db
        migrate(str(db_path))
        assert {"status", "confirmed_at"} <= _columns(conn, "receipts")
        assert "receipt_links" in _tables(conn)
        assert _user_version(conn) == len(MIGRATIONS)

    def test_linked_receipt_backfilled(self, legacy_db):
        db_path, conn = legacy_db
        _seed_legacy_hierarchy(conn)
        r = _seed_legacy_receipt(conn, 1)
        t = _seed_legacy_transaction(conn, receipt_id=r)
        migrate(str(db_path))
        link = conn.execute("SELECT * FROM receipt_links").fetchone()
        assert link["receipt_id"] == r
        assert link["transaction_id"] == t
        assert link["link_source"] == "manual"
        receipt = conn.execute("SELECT * FROM receipts WHERE id = ?", (r,)).fetchone()
        assert receipt["status"] == "linked"
        assert receipt["confirmed_at"] is not None
        # Mirror column preserved
        assert (
            conn.execute(
                "SELECT receipt_id FROM transactions WHERE id = ?", (t,)
            ).fetchone()[0]
            == r
        )

    def test_link_from_soft_deleted_transaction_is_backfilled(self, legacy_db):
        db_path, conn = legacy_db
        _seed_legacy_hierarchy(conn)
        r = _seed_legacy_receipt(conn, 1)
        t = _seed_legacy_transaction(conn, receipt_id=r, deleted=True)
        migrate(str(db_path))
        link = conn.execute("SELECT * FROM receipt_links").fetchone()
        assert link["transaction_id"] == t
        assert conn.execute("SELECT status FROM receipts WHERE id = ?", (r,)).fetchone()[0] == "linked"

    def test_receipt_referenced_by_live_and_deleted_transaction_links_to_live(self, legacy_db):
        db_path, conn = legacy_db
        _seed_legacy_hierarchy(conn)
        r = _seed_legacy_receipt(conn, 1)
        t_dead = _seed_legacy_transaction(conn, receipt_id=r, deleted=True)
        t_live = _seed_legacy_transaction(conn, receipt_id=r)
        migrate(str(db_path))   # must not raise on UNIQUE(receipt_id)
        links = conn.execute("SELECT transaction_id FROM receipt_links").fetchall()
        assert [row[0] for row in links] == [t_live]

    def test_confirmed_unlinked_receipt_becomes_unlinked(self, legacy_db):
        db_path, conn = legacy_db
        r = _seed_legacy_receipt(conn, 1, vendor="Shop")
        migrate(str(db_path))
        receipt = conn.execute("SELECT * FROM receipts WHERE id = ?", (r,)).fetchone()
        assert receipt["status"] == "unlinked"
        assert receipt["confirmed_at"] == receipt["updated_at"]

    def test_unconfirmed_receipt_stays_pending(self, legacy_db):
        db_path, conn = legacy_db
        r = _seed_legacy_receipt(conn, 1, vendor=None)
        migrate(str(db_path))
        receipt = conn.execute("SELECT * FROM receipts WHERE id = ?", (r,)).fetchone()
        assert receipt["status"] == "pending"
        assert receipt["confirmed_at"] is None

    def test_mixed_population(self, legacy_db):
        db_path, conn = legacy_db
        _seed_legacy_hierarchy(conn)
        linked = _seed_legacy_receipt(conn, 1)
        _seed_legacy_transaction(conn, receipt_id=linked)
        unlinked = _seed_legacy_receipt(conn, 2)
        pending = _seed_legacy_receipt(conn, 3, vendor=None)
        migrate(str(db_path))
        statuses = dict(conn.execute("SELECT id, status FROM receipts").fetchall())
        assert statuses == {linked: "linked", unlinked: "unlinked", pending: "pending"}
        assert conn.execute("SELECT COUNT(*) FROM receipt_links").fetchone()[0] == 1

    def test_backfill_is_idempotent(self, legacy_db):
        db_path, conn = legacy_db
        _seed_legacy_hierarchy(conn)
        r = _seed_legacy_receipt(conn, 1)
        _seed_legacy_transaction(conn, receipt_id=r)
        migrate(str(db_path))
        migrate(str(db_path))
        assert conn.execute("SELECT COUNT(*) FROM receipt_links").fetchone()[0] == 1

    def test_views_still_queryable(self, legacy_db):
        db_path, conn = legacy_db
        migrate(str(db_path))
        for name in migrations.VIEWS:
            conn.execute(f"SELECT * FROM {name} LIMIT 1").fetchall()

    def test_migrate_from_partially_upgraded_legacy_stamps_without_failing(
        self, legacy_db
    ):
        """Legacy DB that already has the column (e.g. base schema ran on an
        old version) but user_version is behind: guard should stamp, not ALTER."""
        db_path, conn = legacy_db
        conn.execute(
            "ALTER TABLE receipts ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
        )
        migrate(str(db_path))  # must not raise "duplicate column name"
        assert _user_version(conn) == len(MIGRATIONS)
