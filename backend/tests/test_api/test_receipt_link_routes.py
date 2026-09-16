"""
Route tests for Phase 1 receipt linking endpoints. Integration-style:
real SQLite via app_with_db, no repository mocks.
"""

import json

import pytest
from src.services.receipt_links import ReceiptLinkService

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def body(response):
    return json.loads(response.data)


def err(response):
    b = body(response)
    assert b["success"] is False, b
    return b["error"]


def data(response):
    b = body(response)
    assert b["success"] is True, b
    return b["data"]


@pytest.fixture
def link(app_with_db):
    def _link(receipt_id, txn_id):
        with app_with_db.app_context():
            return ReceiptLinkService().link(receipt_id, txn_id)

    return _link


@pytest.fixture
def receipt_file(tmp_path):
    """A real file on disk so /receipts/confirm's existence check passes."""
    p = tmp_path / "r.jpg"
    p.write_bytes(b"\xff\xd8\xff\xd9")
    return str(p)


@pytest.fixture
def unlinked(app_with_db, test_data):
    return test_data.create_receipt(
        app_with_db,
        status="unlinked",
        vendor="Tesco",
        date="2024-01-15",
        amount=23.40,
        confirmed_at="2024-01-16 10:00:00.000",
    )


@pytest.fixture
def pending(app_with_db, test_data, receipt_file):
    return test_data.create_receipt(
        app_with_db,
        status="pending",
        vendor=None,
        date="2024-01-15",
        amount=23.40,
        file_path=receipt_file,
    )


# --------------------------------------------------------------------------- #
# GET /receipts
# --------------------------------------------------------------------------- #


class TestListReceipts:
    @pytest.fixture
    def population(self, app_with_db, test_data, make_transaction, link):
        p =test_data.create_receipt(
            app_with_db,
            status='pending',
            vendor=None,
            date=None,
            amount=None
            )

        u1 = test_data.create_receipt(
            app_with_db,
            status="unlinked",
            vendor="Tesco",
            date="2024-01-15",
            amount=23.40,
        )
        u2 = test_data.create_receipt(
            app_with_db,
            status="unlinked",
            vendor="Boots",
            date="2024-02-01",
            amount=9.99,
        )
        l = test_data.create_receipt(
            app_with_db,
            status="unlinked",
            vendor="Argos",
            date="2024-01-18",
            amount=40.00,
        )
        txn = make_transaction(transaction_date="2024-01-18", amount=-40.00)
        link(l, txn)
        return {"pending": p, "u1": u1, "u2": u2, "linked": l, "txn": txn}

    def test_default_returns_all_with_pagination(self, client, population):
        d = data(client.get("/api/receipts"))
        assert len(d["receipts"]) == 4
        assert d["pagination"] == {
            "limit": 50,
            "offset": 0,
            "total": 4,
            "count": 4,
            "has_more": False,
        }

    def test_receipt_shape_includes_link_state(self, client, population):
        d = data(client.get(f"/api/receipts?status=linked"))
        r = d["receipts"][0]
        assert r["id"] == population["linked"]
        assert r["status"] == "linked"
        assert r["linked_transaction_id"] == population["txn"]
        assert r["confirmed_at"] is not None
        assert "file_path" not in r

    def test_status_filter_comma_separated(self, client, population):
        d = data(client.get("/api/receipts?status=pending,unlinked"))
        ids = {r["id"] for r in d["receipts"]}
        assert ids == {population["pending"], population["u1"], population["u2"]}
        assert d["filters"]["status"] == ["pending", "unlinked"]

    def test_invalid_status_is_400(self, client, population):
        e = err(client.get("/api/receipts?status=saved"))
        assert e["code"] == "INVALID_VALUE"
        assert e["field"] == "status"

    def test_vendor_filter(self, client, population):
        d = data(client.get("/api/receipts?vendor=tes"))
        assert [r["id"] for r in d["receipts"]] == [population["u1"]]

    def test_date_range_new_and_legacy_param_names(self, client, population):
        new = data(client.get("/api/receipts?date_from=2024-01-15&date_to=2024-01-20"))
        old = data(
            client.get("/api/receipts?start_date=2024-01-15&end_date=2024-01-20")
        )
        assert {r["id"] for r in new["receipts"]} == {
            population["u1"],
            population["linked"],
        }
        assert new["receipts"] == old["receipts"]

    def test_invalid_date_is_400(self, client, population):
        e = err(client.get("/api/receipts?date_from=15-01-2024"))
        assert e["code"] == "INVALID_VALUE"
        assert e["field"] == "date_from"

    def test_amount_range(self, client, population):
        d = data(client.get("/api/receipts?amount_min=10&amount_max=30"))
        assert [r["id"] for r in d["receipts"]] == [population["u1"]]

    def test_q_search(self, client, population):
        d = data(client.get("/api/receipts?q=boots"))
        assert [r["id"] for r in d["receipts"]] == [population["u2"]]

    def test_pagination_has_more(self, client, population):
        d = data(client.get("/api/receipts?limit=3"))
        assert d["pagination"]["count"] == 3
        assert d["pagination"]["total"] == 4
        assert d["pagination"]["has_more"] is True
        d = data(client.get("/api/receipts?limit=3&offset=3"))
        assert d["pagination"]["count"] == 1
        assert d["pagination"]["has_more"] is False

    def test_sort(self, client, population):
        d = data(
            client.get("/api/receipts?sort=amount&direction=asc&status=unlinked,linked")
        )
        assert [r["amount"] for r in d["receipts"]] == [9.99, 23.40, 40.00]

    def test_invalid_sort_is_400(self, client, population):
        e = err(client.get("/api/receipts?sort=file_path"))
        assert e["code"] == "INVALID_VALUE"
        assert e["field"] == "sort"

    @pytest.mark.parametrize(
        "qs,field",
        [
            ("limit=0", "limit"),
            ("limit=501", "limit"),
            ("offset=-1", "offset"),
            ("min_confidence=4", "min_confidence"),
            ("direction=up", "direction"),
        ],
    )
    def test_bad_paging_params_are_400(self, client, population, qs, field):
        e = err(client.get(f"/api/receipts?{qs}"))
        assert e["code"] == "INVALID_VALUE"
        assert e["field"] == field


# --------------------------------------------------------------------------- #
# GET /receipts/summary
# --------------------------------------------------------------------------- #


class TestSummary:
    def test_empty(self, client):
        assert data(client.get("/api/receipts/summary")) == {
            "pending": 0,
            "unlinked": 0,
            "linked": 0,
        }

    def test_counts(
        self, client, app_with_db, test_data, unlinked, pending, make_transaction, link
    ):
        l = test_data.create_receipt(app_with_db, status="unlinked")
        link(l, make_transaction())
        assert data(client.get("/api/receipts/summary")) == {
            "pending": 1,
            "unlinked": 1,
            "linked": 1,
        }

    def test_summary_not_shadowed_by_id_route(self, client):
        """'/receipts/summary' must not be routed to GET /receipts/<int:id>."""
        assert client.get("/api/receipts/summary").status_code == 200


# --------------------------------------------------------------------------- #
# GET /receipts/<id>
# --------------------------------------------------------------------------- #


class TestGetReceipt:
    def test_detail_includes_link_state(self, client, unlinked, make_transaction, link):
        txn = make_transaction()
        link(unlinked, txn)
        d = data(client.get(f"/api/receipts/{unlinked}"))["receipt"]
        assert d["status"] == "linked"
        assert d["linked_transaction_id"] == txn
        assert d["confirmed_at"] is not None
        assert "raw_text" in d and "stored_filename" in d

    def test_not_found(self, client):
        r = client.get("/api/receipts/999999")
        assert r.status_code == 404
        assert err(r)["entity"] == "Receipt"


# --------------------------------------------------------------------------- #
# GET /receipts/<id>/candidates
# --------------------------------------------------------------------------- #


class TestCandidates:
    def test_uses_receipt_fields_and_config_tolerance(
        self, client, app_with_db, unlinked, make_transaction
    ):
        assert app_with_db.config["RECEIPT_MATCH_DATE_TOLERANCE_DAYS"] == 5
        inside = make_transaction(
            transaction_date="2024-01-20", amount=-23.40
        )  # +5 days
        outside = make_transaction(
            transaction_date="2024-01-21", amount=-23.40
        )  # +6 days
        wrong_amount = make_transaction(transaction_date="2024-01-15", amount=-23.50)
        d = data(client.get(f"/api/receipts/{unlinked}/candidates"))
        ids = {t["id"] for t in d["transactions"]}
        assert inside in ids
        assert outside not in ids
        assert wrong_amount not in ids

    def test_excludes_already_linked_transactions(
        self, client, app_with_db, test_data, unlinked, make_transaction, link
    ):
        taken = make_transaction(transaction_date="2024-01-15", amount=-23.40)
        free = make_transaction(transaction_date="2024-01-15", amount=-23.40)
        link(test_data.create_receipt(app_with_db, status="unlinked"), taken)
        ids = {
            t["id"]
            for t in data(client.get(f"/api/receipts/{unlinked}/candidates"))[
                "transactions"
            ]
        }
        assert free in ids
        assert taken not in ids

    def test_candidates_respect_config_override(
        self, tmp_path, test_data, make_transaction
    ):
        """Tolerance is read from app config, not hard-coded."""
        from src.api.app import create_app
        from src.database import connection as db

        app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(tmp_path / "t.db"),
                "RECEIPT_MATCH_DATE_TOLERANCE_DAYS": 1,
            }
        )
        try:
            rid = test_data.create_receipt(
                app, status="unlinked", date="2024-01-15", amount=10.0
            )
            h = test_data.create_full_hierarchy(app)
            up = test_data.create_upload(app)
            near = test_data.create_transaction(
                app, up, h["party_id"], transaction_date="2024-01-16", amount=-10.0
            )
            far = test_data.create_transaction(
                app, up, h["party_id"], transaction_date="2024-01-18", amount=-10.0
            )
            ids = {
                t["id"]
                for t in data(app.test_client().get(f"/api/receipts/{rid}/candidates"))[
                    "transactions"
                ]
            }
            assert near in ids and far not in ids
        finally:
            db.close_manager()

    def test_receipt_with_no_searchable_fields_returns_empty(
        self, client, app_with_db, test_data
    ):
        rid = test_data.create_receipt(
            app_with_db, status="pending", vendor=None, date=None, amount=None
        )
        d = data(client.get(f"/api/receipts/{rid}/candidates"))
        assert d["transactions"] == []

    def test_not_found(self, client):
        assert client.get("/api/receipts/999999/candidates").status_code == 404


# --------------------------------------------------------------------------- #
# POST /receipts/<id>/link  +  DELETE /receipts/<id>/link
# --------------------------------------------------------------------------- #


class TestLinkRoutes:
    def test_link(self, client, unlinked, live_transaction):
        r = client.post(
            f"/api/receipts/{unlinked}/link", json={"transaction_id": live_transaction}
        )
        assert r.status_code == 200
        d = data(r)
        assert d["receipt"]["status"] == "linked"
        assert d["receipt"]["linked_transaction_id"] == live_transaction
        assert d["transaction"]["id"] == live_transaction
        assert d["transaction"]["receipt_id"] == unlinked

    def test_link_returns_transaction_with_hierarchy(
        self, client, unlinked, live_transaction
    ):
        d = data(
            client.post(
                f"/api/receipts/{unlinked}/link",
                json={"transaction_id": live_transaction},
            )
        )
        assert (
            "party_name" in d["transaction"]
        )  # same shape as other transaction responses

    def test_link_requires_transaction_id(self, client, unlinked):
        e = err(client.post(f"/api/receipts/{unlinked}/link", json={}))
        assert e["code"] == "REQUIRED_FIELD"
        assert e["field"] == "transaction_id"

    def test_link_rejects_non_int(self, client, unlinked):
        e = err(
            client.post(
                f"/api/receipts/{unlinked}/link", json={"transaction_id": "abc"}
            )
        )
        assert e["code"] == "INVALID_VALUE"
        assert e["field"] == "transaction_id"

    def test_link_conflict_receipt(self, client, unlinked, make_transaction, link):
        t1, t2 = make_transaction(), make_transaction()
        link(unlinked, t1)
        r = client.post(f"/api/receipts/{unlinked}/link", json={"transaction_id": t2})
        assert r.status_code == 409
        e = err(r)
        assert e["code"] == "CONFLICT"
        assert e["entity"] == "Receipt"
        assert e["details"]["transaction_id"] == t1

    def test_link_conflict_transaction(
        self, client, app_with_db, test_data, unlinked, live_transaction, link
    ):
        other = test_data.create_receipt(app_with_db, status="unlinked")
        link(other, live_transaction)
        r = client.post(
            f"/api/receipts/{unlinked}/link", json={"transaction_id": live_transaction}
        )
        assert r.status_code == 409
        assert err(r)["entity"] == "Transaction"

    def test_link_receipt_not_found(self, client, live_transaction):
        r = client.post(
            "/api/receipts/999999/link", json={"transaction_id": live_transaction}
        )
        assert r.status_code == 404
        assert err(r)["entity"] == "Receipt"

    def test_link_transaction_not_found(self, client, unlinked):
        r = client.post(
            f"/api/receipts/{unlinked}/link", json={"transaction_id": 999999}
        )
        assert r.status_code == 404
        assert err(r)["entity"] == "Transaction"

    def test_unlink(self, client, unlinked, live_transaction, link):
        link(unlinked, live_transaction)
        r = client.delete(f"/api/receipts/{unlinked}/link")
        assert r.status_code == 200
        d = data(r)
        assert d["receipt"]["status"] == "unlinked"
        assert d["receipt"]["linked_transaction_id"] is None
        assert d["transaction"]["receipt_id"] is None

    def test_unlink_idempotent(self, client, unlinked):
        r = client.delete(f"/api/receipts/{unlinked}/link")
        assert r.status_code == 200
        assert data(r)["transaction"] is None

    def test_unlink_not_found(self, client):
        assert client.delete("/api/receipts/999999/link").status_code == 404


# --------------------------------------------------------------------------- #
# POST /receipts/confirm
# --------------------------------------------------------------------------- #


class TestConfirm:
    def _payload(self, rid, path, **over):
        p = {
            "id": rid,
            "original_filename": "r.jpg",
            "file_path": path,
            "vendor": "Tesco",
            "amount": 23.40,
            "date": "2024-01-15",
            "confidence": 2,
        }
        p.update(over)
        return p

    def test_confirm_promotes_pending_to_unlinked(self, client, pending, receipt_file):
        r = client.post(
            "/api/receipts/confirm", json=self._payload(pending, receipt_file)
        )
        assert r.status_code == 201
        d = data(r)["receipt"]
        assert d["status"] == "unlinked"
        assert d["confirmed_at"] is not None
        assert d["vendor"] == "Tesco"
        assert d["date"].startswith("2024-01-15")

    def test_confirm_date_stored_as_date_not_timestamp(
        self, client, app_with_db, test_data, pending, receipt_file
    ):
        client.post("/api/receipts/confirm", json=self._payload(pending, receipt_file))
        raw = test_data.fetch_one(
            app_with_db, "SELECT date FROM receipts WHERE id = ?", (pending,)
        )
        assert raw["date"] == "2024-01-15"

    def test_confirm_linked_receipt_keeps_status(
        self, client, app_with_db, test_data, receipt_file, live_transaction, link
    ):
        rid = test_data.create_receipt(
            app_with_db, status="unlinked", file_path=receipt_file
        )
        link(rid, live_transaction)
        d = data(
            client.post(
                "/api/receipts/confirm",
                json=self._payload(rid, receipt_file, vendor="Edited"),
            )
        )["receipt"]
        assert d["status"] == "linked"
        assert d["vendor"] == "Edited"

    def test_confirm_requires_vendor(self, client, pending, receipt_file):
        e = err(
            client.post(
                "/api/receipts/confirm",
                json=self._payload(pending, receipt_file, vendor=""),
            )
        )
        assert e["code"] in ("REQUIRED_FIELD", "INVALID_VALUE")

    def test_confirm_unknown_receipt(self, client, receipt_file):
        r = client.post(
            "/api/receipts/confirm", json=self._payload(999999, receipt_file)
        )
        assert r.status_code == 404


# --------------------------------------------------------------------------- #
# DELETE /receipts/<id>
# --------------------------------------------------------------------------- #


class TestDelete:
    def test_delete_unlinked(self, client, unlinked):
        assert client.delete(f"/api/receipts/{unlinked}").status_code == 200
        assert client.get(f"/api/receipts/{unlinked}").status_code == 404

    def test_delete_linked_is_409(
        self, client, app_with_db, test_data, unlinked, live_transaction, link
    ):
        link(unlinked, live_transaction)
        r = client.delete(f"/api/receipts/{unlinked}")
        assert r.status_code == 409
        e = err(r)
        assert e["code"] == "HAS_DEPENDENCIES"
        assert e["details"]["dependency"] == "transaction"
        assert e["details"]["transaction_id"] == live_transaction
        # Nothing changed
        assert (
            test_data.fetch_one(
                app_with_db, "SELECT status FROM receipts WHERE id = ?", (unlinked,)
            )["status"]
            == "linked"
        )

    def test_delete_linked_with_force(
        self, client, app_with_db, test_data, unlinked, live_transaction, link
    ):
        link(unlinked, live_transaction)
        r = client.delete(f"/api/receipts/{unlinked}?force=true")
        assert r.status_code == 200
        assert client.get(f"/api/receipts/{unlinked}").status_code == 404
        txn = test_data.fetch_one(
            app_with_db,
            "SELECT receipt_id FROM transactions WHERE id = ?",
            (live_transaction,),
        )
        assert txn["receipt_id"] is None
        assert (
            test_data.fetch_one(app_with_db, "SELECT COUNT(*) AS n FROM receipt_links")[
                "n"
            ]
            == 0
        )


# --------------------------------------------------------------------------- #
# Transactions side
# --------------------------------------------------------------------------- #


class TestTransactionRoutes:
    def test_link_receipt_goes_through_service(
        self, client, app_with_db, test_data, unlinked, live_transaction
    ):
        r = client.post(
            f"/api/transactions/{live_transaction}/link-receipt",
            json={"receipt_id": unlinked},
        )
        assert r.status_code == 200
        assert data(r)["receipt_id"] == unlinked
        row = test_data.fetch_one(
            app_with_db, "SELECT * FROM receipts WHERE id = ?", (unlinked,)
        )
        assert row["status"] == "linked"
        assert (
            test_data.fetch_one(app_with_db, "SELECT COUNT(*) AS n FROM receipt_links")[
                "n"
            ]
            == 1
        )

    def test_link_receipt_conflict_is_409(
        self, client, app_with_db, test_data, unlinked, live_transaction, link
    ):
        link(test_data.create_receipt(app_with_db, status="unlinked"), live_transaction)
        r = client.post(
            f"/api/transactions/{live_transaction}/link-receipt",
            json={"receipt_id": unlinked},
        )
        assert r.status_code == 409

    def test_search_uses_config_tolerances(self, client, app_with_db, make_transaction):
        inside = make_transaction(transaction_date="2024-01-20", amount=-23.40)
        outside = make_transaction(transaction_date="2024-01-21", amount=-23.40)
        d = data(
            client.post(
                "/api/transactions/search",
                json={"transaction_date": "2024-01-15", "amount": -23.40},
            )
        )
        ids = {t["id"] for t in d["transactions"]}
        assert inside in ids and outside not in ids


class TestCancel:
    def test_cancel_pending(self, client, pending):
        r = client.post(f'/api/receipts/{pending}/cancel')
        assert r.status_code == 200
        assert data(r)['deleted_receipt']['id'] == pending
        assert 'file_path' not in data(r)['deleted_receipt']
        assert client.get(f'/api/receipts/{pending}').status_code == 404

    def test_cancel_unlinked_is_409(self, client, unlinked):
        r = client.post(f'/api/receipts/{unlinked}/cancel')
        assert r.status_code == 409
        assert err(r)['code'] == 'CONFLICT'
        assert client.get(f'/api/receipts/{unlinked}').status_code == 200

    def test_cancel_linked_is_409_and_link_intact(self, client, app_with_db, test_data, unlinked, live_transaction, link):
        link(unlinked, live_transaction)
        assert client.post(f'/api/receipts/{unlinked}/cancel').status_code == 409
        assert test_data.fetch_one(app_with_db, 'SELECT COUNT(*) AS n FROM receipt_links')['n'] == 1

    def test_cancel_not_found(self, client):
        assert client.post('/api/receipts/999999/cancel').status_code == 404


class TestUpdateReceipt:
    def test_put_ignores_link_state_fields(self, client, app_with_db, test_data, unlinked, live_transaction, link):
        link(unlinked, live_transaction)
        r = client.put(f'/api/receipts/{unlinked}', json={'vendor': 'Edited', 'status': 'pending',
                                                          'confirmed_at': None, 'linked_transaction_id': None})
        assert r.status_code == 200
        d = data(r)['receipt']
        assert d['vendor'] == 'Edited'
        assert d['status'] == 'linked'
        assert d['linked_transaction_id'] == live_transaction
        
    def test_put_only_link_state_fields_is_400(self, client, unlinked):
        e = err(client.put(f'/api/receipts/{unlinked}', json={'status': 'linked'}))
        assert e['code'] == 'INVALID_VALUE'   # "No valid fields to update", not a 500
