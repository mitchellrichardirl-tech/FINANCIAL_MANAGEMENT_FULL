"""
Contract: the bulk-upload pipeline persists every successfully processed
receipt as status='pending' BEFORE its success event is emitted. This is
what makes abandoned upload sessions recoverable via the Unlinked view
(receipt-links Phase 1).

Tested through AsyncReceiptStreamProcessor.process_files — a plain sync
generator — with the Gemini extractor stubbed. wc.load_pages and
wc.persist run for real, so the temp files must be decodable images and
the DB row is genuinely written by the production persistence path.
"""
import json
import numpy as np
import pytest

import src.api.services.async_processor as processor_module
from src.api.services.async_processor import AsyncReceiptStreamProcessor


# --------------------------------------------------------------------------- #
# Stubs & helpers
# --------------------------------------------------------------------------- #
class StubExtractor:
    """Stands in for MultimodalExtractor: populates the Receipt without a
    network call. Matches the interface receipt_worker_async uses:
    `await extractor.aprocess_receipt(page)` -> Receipt."""

    def __init__(self, fail_for: set[str] | None = None):
        self.fail_for = fail_for or set()
        self.calls = 0

    async def aprocess_receipt(self, receipt):
        self.calls += 1
        name = str(receipt.original_filename)
        if any(name.endswith(target) for target in self.fail_for):
            raise RuntimeError("stub extraction failure")
        receipt.vendor = "Stub Vendor"
        receipt.amount = 12.34
        receipt.confidence = 2
        return receipt


@pytest.fixture
def stub_extractor(monkeypatch):
    """Patch create_extractor where async_processor imported it."""
    stub = StubExtractor()
    monkeypatch.setattr(processor_module, "create_extractor", lambda kind, cfg: stub)
    return stub


@pytest.fixture
def make_temp_files(tmp_path):
    """(identifier, temp_path) pairs as the route hands them over.
    Real (tiny) images, because wc.load_pages decodes them."""
    import cv2

    def _make(names=("receipt_a.jpg",)):
        out = []
        for name in names:
            p = tmp_path / f"tmp_{name}"
            cv2.imwrite(str(p), np.full((12, 12, 3), 255, dtype=np.uint8))
            out.append((name, str(p)))
        return out
    return _make


def parse_event(raw: str) -> dict:
    """SSE event string -> payload dict. Heartbeat comments -> {}."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def drain(gen):
    return [e for e in (parse_event(raw) for raw in gen if raw) if e]


@pytest.fixture
def processor(app_with_db, tmp_path, stub_extractor):
    upload_folder = tmp_path / "uploads"
    upload_folder.mkdir()
    with app_with_db.app_context():
        yield AsyncReceiptStreamProcessor(
            upload_folder=upload_folder,
            max_concurrency=2,
            task_timeout=30,
            stream_timeout=60,
            heartbeat_interval=1,
        )


# --------------------------------------------------------------------------- #
# The contract
# --------------------------------------------------------------------------- #
class TestPendingPersistenceContract:

    def test_success_event_refers_to_an_already_persisted_pending_receipt(
        self, processor, make_temp_files, app_with_db, test_data
    ):
        """At the moment a success event is observable by the client, the
        receipt row must already exist with status='pending'. Checked
        interleaved: the generator is lazy, so the assertion runs before
        any later event is produced."""
        seen_success = False
        for raw in processor.process_files(make_temp_files(["receipt_a.jpg"])):
            event = parse_event(raw)
            if event.get("status") != "success":
                continue
            seen_success = True

            row = test_data.fetch_one(
                app_with_db,
                "SELECT status, confirmed_at FROM receipts WHERE id = ?",
                (event["receipt_id"],),
            )
            assert row is not None, "success event emitted before receipt persisted"
            assert row["status"] == "pending"
            assert row["confirmed_at"] is None

        assert seen_success, "no success event emitted"

    def test_success_payload_shape(self, processor, make_temp_files):
        events = drain(processor.process_files(make_temp_files(["receipt_a.jpg"])))
        successes = [e for e in events if e.get("status") == "success"]
        assert len(successes) == 1

        e = successes[0]
        # Envelope (SSEEventBuilder)
        assert e["filename"] == "receipt_a.jpg"          # identifier
        assert "file_index" in e and "progress" in e
        # Worker payload (flattened result_data)
        assert e["receipt_id"] > 0
        assert e["receipt_status"] == "pending"
        assert e["original_filename"] == "receipt_a.jpg"
        assert e["stored_filename"]
        assert e["extracted_data"]["vendor"] == "Stub Vendor"
        assert e["extracted_data"]["amount"] == 12.34
        assert e["extracted_data"]["date"] is None

    def test_result_data_cannot_clobber_event_envelope(self):
        from pathlib import Path
        from src.models.receipt import Receipt
        from src.receipts import worker_common as wc

        RESERVED = {"status", "file_index", "filename", "progress", "timestamp"}
        result = wc.success(0, "x.jpg", 1, Receipt(original_filename=Path("x.jpg"), page_number=0), "stored.jpg")
        assert not (set(result.data) & RESERVED), f"payload uses reserved envelope keys: {set(result.data) & RESERVED}"
        assert result.data["receipt_status"] == "pending"

    def test_every_file_in_batch_is_persisted(
        self, processor, make_temp_files, app_with_db, test_data
    ):
        names = ["a.jpg", "b.jpg", "c.jpg"]
        events = drain(processor.process_files(make_temp_files(names)))

        ids = [e["receipt_id"] for e in events if e.get("status") == "success"]
        assert len(ids) == 3
        for rid in ids:
            row = test_data.fetch_one(
                app_with_db, "SELECT status FROM receipts WHERE id = ?", (rid,)
            )
            assert row["status"] == "pending"

        completed = [e for e in events if e.get("status") == "completed"]
        assert completed and completed[0]["successes"] == 3

    def test_failed_extraction_leaves_no_row(
        self, processor, stub_extractor, make_temp_files, app_with_db, test_data
    ):
        """The worker persists AFTER extraction (wc.persist follows
        aprocess_receipt), so a failed extraction must leave no row.
        Pinned deliberately: if we later decide failed extractions should
        persist the image for manual entry, this test changes with it."""
        stub_extractor.fail_for = {"bad.jpg"}
        events = drain(processor.process_files(make_temp_files(["bad.jpg", "good.jpg"])))

        assert {e["status"] for e in events} >= {"success", "error"}
        error = next(e for e in events if e.get("status") == "error")
        assert error["filename"] == "bad.jpg"
        assert "stub extraction failure" in error["error"]

        count = test_data.fetch_one(app_with_db, "SELECT COUNT(*) AS n FROM receipts")
        assert count["n"] == 1   # only good.jpg

    def test_abandoned_receipts_are_listable(
        self, processor, make_temp_files, app_with_db
    ):
        """End-to-end tie to the feature: a receipt from a 'forgotten'
        session shows up in the Unlinked view's source query."""
        from src.database.repositories.receipts import ReceiptRepository

        drain(processor.process_files(make_temp_files(["orphan.jpg"])))
        with app_with_db.app_context():
            rows, total = ReceiptRepository().list(status=["pending"])
        assert total == 1
        assert rows[0]["original_filename"]   # present and non-empty
        assert rows[0]["linked_transaction_id"] is None