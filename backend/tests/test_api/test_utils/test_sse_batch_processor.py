"""
Tests for BatchProcessor in src/api/utils/sse.py.

NOTE: BatchProcessor has no callers anywhere in src/ - the live streaming paths
all go through StreamEventReporter + ParallelStreamProcessor /
AsyncReceiptStreamProcessor. These tests pin its current behaviour so the
class is safe to either keep or delete deliberately rather than by accident.
See backlog item 20, which recommends deleting it.

The tests also document where its event protocol has drifted from
StreamEventReporter's, which is the main argument against keeping it.
"""
import json

import pytest

from src.api.utils.sse import BatchProcessor, ProgressInfo


def parse(raw: str) -> dict:
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def statuses(events):
    return [parse(e)["status"] for e in events]


def identity(item):
    return str(item)


@pytest.fixture
def run():
    """Run a BatchProcessor to exhaustion and return the raw SSE chunks."""
    def _run(items, processor=None, get_identifier=identity, max_workers=4):
        batch = BatchProcessor(items, max_workers=max_workers)
        processor = processor or (lambda index, item: {"value": item})
        return list(batch.process_sequential(processor, get_identifier)), batch
    return _run


# --------------------------------------------------------------------------- #
# ProgressInfo (used by every event builder)
# --------------------------------------------------------------------------- #
class TestProgressInfo:

    def test_percentage(self):
        assert ProgressInfo(current=1, total=4).percentage == 25.0

    def test_percentage_of_zero_total_is_zero_not_an_error(self):
        assert ProgressInfo(current=0, total=0).percentage == 0

    def test_to_dict(self):
        assert ProgressInfo(current=2, total=4).to_dict() == {
            "current": 2, "total": 4, "percentage": 50.0
        }

    def test_percentage_is_not_clamped(self):
        assert ProgressInfo(current=5, total=4).percentage == 125.0


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #
class TestConstruction:

    def test_total_is_derived_from_the_items(self):
        assert BatchProcessor(["a", "b", "c"]).total == 3

    def test_progress_starts_at_zero(self):
        batch = BatchProcessor(["a"])
        assert batch.processed_count == 0
        assert batch.get_progress().to_dict() == {
            "current": 0, "total": 1, "percentage": 0.0
        }

    def test_increment_progress(self):
        batch = BatchProcessor(["a", "b"])
        batch.increment_progress()
        assert batch.get_progress().current == 1

    def test_max_workers_defaults_to_four(self):
        assert BatchProcessor([]).max_workers == 4

    def test_max_workers_is_stored_but_unused(self):
        """process_sequential reports workers=1 regardless - see backlog 20."""
        batch = BatchProcessor(["a"], max_workers=8)
        assert batch.max_workers == 8
        events = list(batch.process_sequential(lambda i, x: {}, identity))
        assert parse(events[0])["workers"] == 1


# --------------------------------------------------------------------------- #
# event protocol
# --------------------------------------------------------------------------- #
class TestEventProtocol:

    def test_event_sequence(self, run):
        events, _ = run(["a", "b"])
        assert statuses(events) == [
            "starting", "processing", "success", "processing", "success",
            "completed",
        ]

    def test_items_are_processed_in_order(self, run):
        seen = []
        events, _ = run(["a", "b", "c"],
                        processor=lambda index, item: seen.append((index, item)) or {})
        assert seen == [(0, "a"), (1, "b"), (2, "c")]

    def test_starting_event(self, run):
        events, _ = run(["a", "b"])
        event = parse(events[0])
        assert event["total_files"] == 2
        assert event["workers"] == 1

    def test_processing_event_uses_the_identifier_function(self, run):
        events, _ = run([{"name": "x.jpg"}],
                        get_identifier=lambda item: item["name"])
        assert parse(events[1])["filename"] == "x.jpg"

    def test_processing_event_precedes_its_result(self, run):
        events, _ = run(["a"])
        assert parse(events[1])["status"] == "processing"
        assert parse(events[2])["status"] == "success"
        assert parse(events[1])["file_index"] == parse(events[2])["file_index"]

    def test_success_payload_is_flattened(self, run):
        events, _ = run(["a"], processor=lambda i, x: {"receipt_id": 7})
        assert parse(events[2])["receipt_id"] == 7

    def test_empty_item_list(self, run):
        events, _ = run([])
        assert statuses(events) == ["starting", "completed"]
        assert parse(events[-1])["total_processed"] == 0

    def test_events_are_well_formed_sse(self, run):
        events, _ = run(["a"])
        for event in events:
            assert event.startswith("data: ") and event.endswith("\n\n")
            json.loads(event[6:])

    def test_is_lazy(self):
        """Nothing runs until the generator is consumed."""
        calls = []
        batch = BatchProcessor(["a"])
        batch.process_sequential(lambda i, x: calls.append(x) or {}, identity)
        assert calls == []


# --------------------------------------------------------------------------- #
# progress counting
# --------------------------------------------------------------------------- #
class TestProgress:

    def test_processing_event_reports_progress_before_the_item(self, run):
        events, _ = run(["a", "b"])
        first_processing = parse(events[1])["progress"]
        second_processing = parse(events[3])["progress"]
        assert first_processing["current"] == 0
        assert second_processing["current"] == 1

    def test_success_event_reports_progress_after_the_item(self, run):
        events, _ = run(["a", "b"])
        assert parse(events[2])["progress"]["current"] == 1
        assert parse(events[4])["progress"]["current"] == 2

    def test_counter_ends_at_the_total(self, run):
        _, batch = run(["a", "b", "c"])
        assert batch.processed_count == 3

    def test_failures_count_towards_progress(self, run):
        def boom(index, item):
            raise RuntimeError("nope")

        _, batch = run(["a", "b"], processor=boom)
        assert batch.processed_count == 2


# --------------------------------------------------------------------------- #
# failure handling
# --------------------------------------------------------------------------- #
class TestFailures:

    def test_exception_becomes_an_error_event(self, run):
        def boom(index, item):
            raise RuntimeError("nope")

        events, _ = run(["a"], processor=boom)
        error = parse(events[2])
        assert error["status"] == "error"
        assert error["error"] == "nope"
        assert error["filename"] == "a"

    def test_one_failure_does_not_stop_the_batch(self, run):
        def boom_on_b(index, item):
            if item == "b":
                raise RuntimeError("nope")
            return {}

        events, _ = run(["a", "b", "c"], processor=boom_on_b)
        assert statuses(events).count("success") == 2
        assert statuses(events).count("error") == 1
        assert statuses(events)[-1] == "completed"

    def test_error_message_is_the_exception_string(self, run):
        def boom(index, item):
            raise ValueError("bad value: 42")

        events, _ = run(["a"], processor=boom)
        assert parse(events[2])["error"] == "bad value: 42"

    def test_identifier_function_errors_are_not_caught(self, run):
        """get_identifier runs outside the try, so it kills the whole stream."""
        def bad_identifier(item):
            raise KeyError("name")

        with pytest.raises(KeyError):
            run(["a"], get_identifier=bad_identifier)

    def test_base_exceptions_propagate(self, run):
        def boom(index, item):
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            run(["a"], processor=boom)


# --------------------------------------------------------------------------- #
# protocol drift vs StreamEventReporter
# --------------------------------------------------------------------------- #
class TestProtocolDrift:
    """Documents the differences that make this class a liability if kept.
    See backlog item 20."""

    def test_completed_event_omits_the_success_error_tally(self, run):
        """StreamEventReporter.completed() emits successes/errors; this
        doesn't, so a client reading them gets undefined."""
        def boom_on_b(index, item):
            if item == "b":
                raise RuntimeError("nope")
            return {}

        events, _ = run(["a", "b"], processor=boom_on_b)
        completed = parse(events[-1])
        assert completed["total_processed"] == 2
        assert "successes" not in completed
        assert "errors" not in completed

    def test_no_abort_path(self):
        """No way to end a stream early and report what never ran."""
        assert not hasattr(BatchProcessor, "abort")

    def test_no_heartbeat(self):
        """A long sequential batch will sit silent until a proxy times out."""
        assert not hasattr(BatchProcessor, "heartbeat")

    def test_result_data_can_clobber_the_event_envelope(self, run):
        """result_data is spread last, so a payload key called 'status'
        overwrites the event status. StreamEventReporter has the same
        underlying builder, but its payload shape is pinned by a test."""
        events, _ = run(["a"], processor=lambda i, x: {"status": "hijacked"})
        assert parse(events[2])["status"] == "hijacked"