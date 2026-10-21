"""
Tests for src/api/utils/stream_reporter.py.

StreamEventReporter owns the SSE protocol for batch processing: event
sequencing, progress counters, and the abort path. It has no I/O, so these are
plain unit tests - no database, no threads except where thread safety is the
thing under test.

The interesting behaviour is around abort(): it has to report every file the
client saw queued but never got a result for, stay idempotent, and then ignore
late results from workers that were already counted as cancelled.
"""
import json
import threading

import pytest

from src.api.models.processing import ProcessingResult, ProcessingTask
from src.api.utils.stream_reporter import StreamEventReporter


def parse(raw: str) -> dict:
    """SSE chunk -> payload dict. Heartbeat comments -> {}."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def task(index=0, identifier=None):
    return ProcessingTask(
        index=index,
        identifier=identifier or f"file_{index}.jpg",
        data=f"/tmp/{index}",
    )


def success(index=0, identifier=None, data=None):
    return ProcessingResult(
        index=index,
        identifier=identifier or f"file_{index}.jpg",
        success=True,
        data=data if data is not None else {"receipt_id": 100 + index},
    )


def failure(index=0, identifier=None, error="boom"):
    return ProcessingResult(
        index=index,
        identifier=identifier or f"file_{index}.jpg",
        success=False,
        error=error,
    )


@pytest.fixture
def reporter():
    return StreamEventReporter(total=3)


# --------------------------------------------------------------------------- #
# construction
# --------------------------------------------------------------------------- #
class TestConstruction:

    def test_counters_start_at_zero(self, reporter):
        assert (reporter.processed, reporter.successes, reporter.errors) == (0, 0, 0)
        assert reporter.total == 3

    def test_zero_total_is_allowed(self):
        assert StreamEventReporter(total=0).total == 0


# --------------------------------------------------------------------------- #
# lifecycle events
# --------------------------------------------------------------------------- #
class TestStarting:

    def test_reports_the_total(self, reporter):
        event = parse(reporter.starting())
        assert event["status"] == "starting"
        assert event["total_files"] == 3

    def test_metadata_is_passed_through(self, reporter):
        event = parse(reporter.starting(workers=4))
        assert event["workers"] == 4

    def test_arbitrary_metadata_is_allowed(self, reporter):
        event = parse(reporter.starting(workers=2, mode="async"))
        assert event["mode"] == "async"

    def test_does_not_move_the_counters(self, reporter):
        reporter.starting()
        assert reporter.processed == 0


class TestQueued:

    def test_event_shape(self, reporter):
        event = parse(reporter.queued(task(0)))
        assert event["status"] == "processing"
        assert event["file_index"] == 0
        assert event["filename"] == "file_0.jpg"
        assert event["message"] == "Queued for processing..."

    def test_progress_reflects_work_done_not_queued(self, reporter):
        """Queueing is not progress - the counter stays where it was."""
        reporter.queued(task(0))
        event = parse(reporter.queued(task(1)))
        assert event["progress"] == {"current": 0, "total": 3, "percentage": 0.0}

    def test_does_not_move_the_counters(self, reporter):
        reporter.queued(task(0))
        assert (reporter.processed, reporter.errors) == (0, 0)


class TestResult:

    def test_success_event_shape(self, reporter):
        event = parse(reporter.result(success(0)))
        assert event["status"] == "success"
        assert event["file_index"] == 0
        assert event["filename"] == "file_0.jpg"

    def test_success_payload_is_flattened_into_the_event(self, reporter):
        event = parse(reporter.result(success(0, data={"receipt_id": 7})))
        assert event["receipt_id"] == 7

    def test_missing_payload_is_tolerated(self, reporter):
        result = ProcessingResult(index=0, identifier="a.jpg", success=True,
                                  data=None)
        assert parse(reporter.result(result))["status"] == "success"

    def test_error_event_shape(self, reporter):
        event = parse(reporter.result(failure(1, error="ocr died")))
        assert event["status"] == "error"
        assert event["error"] == "ocr died"
        assert event["file_index"] == 1

    def test_missing_error_message_gets_a_default(self, reporter):
        result = ProcessingResult(index=0, identifier="a.jpg", success=False,
                                  error=None)
        assert parse(reporter.result(result))["error"] == "Unknown error"

    def test_counters_track_successes_and_errors(self, reporter):
        reporter.result(success(0))
        reporter.result(failure(1))
        assert (reporter.processed, reporter.successes, reporter.errors) == (2, 1, 1)

    def test_progress_counts_up(self, reporter):
        first = parse(reporter.result(success(0)))["progress"]
        second = parse(reporter.result(success(1)))["progress"]
        assert first["current"] == 1
        assert second["current"] == 2
        assert second["total"] == 3

    def test_percentage_is_derived(self, reporter):
        reporter.result(success(0))
        event = parse(reporter.result(success(1)))
        assert event["progress"]["percentage"] == pytest.approx(200 / 3)

    def test_results_can_exceed_the_total(self, reporter):
        """Nothing clamps the counter - a miscounted total shows up honestly."""
        for i in range(5):
            reporter.result(success(i))
        assert reporter.processed == 5


class TestFailedAndException:

    def test_failed_is_an_error_result(self, reporter):
        event = parse(reporter.failed(task(0), "Timed out after 30s"))
        assert event["status"] == "error"
        assert event["error"] == "Timed out after 30s"
        assert reporter.errors == 1

    def test_exception_wraps_the_message(self, reporter):
        event = parse(reporter.exception(task(0), RuntimeError("kaboom")))
        assert event["error"] == "Processing failed: kaboom"

    def test_exception_counts_as_an_error(self, reporter):
        reporter.exception(task(0), RuntimeError("kaboom"))
        assert (reporter.errors, reporter.successes) == (1, 0)

    def test_failed_clears_the_pending_entry(self, reporter):
        """A file already reported as failed must not be cancelled again."""
        reporter.queued(task(0))
        reporter.queued(task(1))
        reporter.failed(task(0), "timeout")

        cancelled = [parse(e) for e in reporter.abort("stream died")
                     if parse(e).get("cancelled") is True]
        assert [e["filename"] for e in cancelled] == ["file_1.jpg"]
        assert reporter.errors == 2  # the timeout and the cancellation


class TestCompleted:

    def test_reports_the_tally(self, reporter):
        reporter.result(success(0))
        reporter.result(failure(1))
        event = parse(reporter.completed())
        assert event["status"] == "completed"
        assert event["total_processed"] == 2
        assert event["successes"] == 1
        assert event["errors"] == 1

    def test_zero_work(self, reporter):
        event = parse(reporter.completed())
        assert event["total_processed"] == 0

    def test_does_not_move_the_counters(self, reporter):
        reporter.result(success(0))
        reporter.completed()
        assert reporter.processed == 1


class TestHeartbeat:

    def test_is_an_sse_comment(self, reporter):
        assert reporter.heartbeat() == ": heartbeat\n\n"

    def test_carries_no_data(self, reporter):
        assert parse(reporter.heartbeat()) == {}

    def test_does_not_move_the_counters(self, reporter):
        reporter.heartbeat()
        assert reporter.processed == 0


# --------------------------------------------------------------------------- #
# abort
# --------------------------------------------------------------------------- #
class TestAbort:

    def test_cancels_every_pending_file(self, reporter):
        reporter.queued(task(0))
        reporter.queued(task(1))
        events = [parse(e) for e in reporter.abort("stream timed out")]

        cancelled = [e for e in events if e.get("cancelled") is True]
        assert [e["filename"] for e in cancelled] == ["file_0.jpg", "file_1.jpg"]
        assert all("Cancelled: stream timed out" in e["error"] for e in cancelled)

    def test_fatal_event_comes_last(self, reporter):
        reporter.queued(task(0))
        events = [parse(e) for e in reporter.abort("boom")]
        assert events[-1]["fatal"] is True
        assert events[-1]["error"] == "boom"

    def test_fatal_event_carries_the_tally(self, reporter):
        reporter.queued(task(0))
        reporter.queued(task(1))
        reporter.result(success(0))
        fatal = parse(reporter.abort("boom")[-1])

        assert fatal["total_files"] == 3
        assert fatal["total_processed"] == 2
        assert fatal["successes"] == 1
        assert fatal["errors"] == 1
        assert fatal["cancelled"] == 1

    def test_finished_files_are_not_cancelled(self, reporter):
        reporter.queued(task(0))
        reporter.queued(task(1))
        reporter.result(success(0))

        cancelled = [parse(e) for e in reporter.abort("boom")
                     if parse(e).get("cancelled") is True]
        assert [e["filename"] for e in cancelled] == ["file_1.jpg"]

    def test_cancelled_files_count_as_errors(self, reporter):
        reporter.queued(task(0))
        reporter.queued(task(1))
        reporter.abort("boom")
        assert (reporter.processed, reporter.errors) == (2, 2)

    def test_cancellations_are_ordered_by_index(self, reporter):
        for index in (2, 0, 1):
            reporter.queued(task(index))
        cancelled = [parse(e) for e in reporter.abort("boom")
                     if parse(e).get("cancelled") is True]
        assert [e["file_index"] for e in cancelled] == [0, 1, 2]

    def test_abort_with_nothing_pending_is_just_the_fatal_event(self, reporter):
        events = reporter.abort("boom")
        assert len(events) == 1
        assert parse(events[0])["fatal"] is True

    def test_second_abort_returns_nothing(self, reporter):
        reporter.queued(task(0))
        assert reporter.abort("first") != []
        assert reporter.abort("second") == []

    def test_second_abort_does_not_move_the_counters(self, reporter):
        reporter.queued(task(0))
        reporter.abort("first")
        snapshot = (reporter.processed, reporter.errors)
        reporter.abort("second")
        assert (reporter.processed, reporter.errors) == snapshot


class TestLateResultsAfterAbort:
    """The race the async processor actually hits: the stream times out and
    reports a file as cancelled, then the worker finishes and reports it
    again. The second report must be dropped, not double-counted."""

    def test_late_result_returns_an_empty_string(self, reporter):
        reporter.queued(task(0))
        reporter.abort("stream timed out")
        assert reporter.result(success(0)) == ""

    def test_late_result_does_not_move_the_counters(self, reporter):
        reporter.queued(task(0))
        reporter.abort("stream timed out")
        snapshot = (reporter.processed, reporter.successes, reporter.errors)

        reporter.result(success(0))
        reporter.result(failure(1))

        assert (reporter.processed, reporter.successes,
                reporter.errors) == snapshot

    def test_late_failure_is_also_dropped(self, reporter):
        reporter.queued(task(0))
        reporter.abort("stream timed out")
        assert reporter.failed(task(0), "timed out") == ""

    def test_empty_string_is_falsy_for_the_caller(self, reporter):
        """async_processor skips falsy payloads - that's what suppresses them."""
        reporter.queued(task(0))
        reporter.abort("boom")
        assert not reporter.result(success(0))

    def test_completed_after_abort_still_reports_the_abort_tally(self, reporter):
        reporter.queued(task(0))
        reporter.abort("boom")
        reporter.result(success(0))  # dropped
        assert parse(reporter.completed())["errors"] == 1


# --------------------------------------------------------------------------- #
# thread safety
# --------------------------------------------------------------------------- #
class TestThreadSafety:
    """The async processor calls queued()/result() from the event-loop thread
    and abort()/heartbeat() from the request thread."""

    def test_concurrent_results_are_all_counted(self):
        reporter = StreamEventReporter(total=200)
        barrier = threading.Barrier(4)

        def report(start):
            barrier.wait()
            for index in range(start, start + 50):
                reporter.result(success(index))

        threads = [threading.Thread(target=report, args=(i * 50,))
                   for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert reporter.processed == 200
        assert reporter.successes == 200

    def test_concurrent_abort_only_fires_once(self):
        reporter = StreamEventReporter(total=10)
        for index in range(10):
            reporter.queued(task(index))

        barrier = threading.Barrier(5)
        results = []

        def do_abort():
            barrier.wait()
            results.append(reporter.abort("boom"))

        threads = [threading.Thread(target=do_abort) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        non_empty = [r for r in results if r]
        assert len(non_empty) == 1
        assert len(non_empty[0]) == 11  # 10 cancellations + 1 fatal
        assert reporter.errors == 10

    def test_abort_racing_results_never_double_counts(self):
        """Whichever order they interleave, each file is counted exactly once."""
        reporter = StreamEventReporter(total=20)
        for index in range(20):
            reporter.queued(task(index))

        barrier = threading.Barrier(2)

        def report_results():
            barrier.wait()
            for index in range(20):
                reporter.result(success(index))

        def do_abort():
            barrier.wait()
            reporter.abort("boom")

        threads = [threading.Thread(target=report_results),
                   threading.Thread(target=do_abort)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert reporter.processed == 20
        assert reporter.successes + reporter.errors == 20