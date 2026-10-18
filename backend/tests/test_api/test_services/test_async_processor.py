"""
Tests for src/api/services/async_processor.py.

`test_receipt_stream_processor.py` covers the persistence contract end to end
with real images and a real database. This file covers the streaming machinery
instead: config resolution, event ordering, the two timeouts, heartbeats,
thread death, and client disconnect.

To do that the worker itself is replaced (`receipt_worker_async` is a module
attribute, so monkeypatching it is enough) with a controllable coroutine. That
keeps the tests off OCR and the filesystem, and lets the timeouts run in
fractions of a second rather than the production 180s/900s.

Timing note: every test drives sub-second timeouts. Assertions are written
against ordering and event content rather than wall-clock values, so a slow CI
box makes them slower, not flaky - except where a test explicitly needs a
worker to outlive a timeout, where the margins are wide (10x).
"""
import json
import threading
import time

import pytest

import src.api.services.async_processor as processor_module
from src.api.models.processing import ProcessingResult
from src.api.services.async_processor import (
    DEFAULT_HEARTBEAT,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_STREAM_TIMEOUT,
    DEFAULT_TASK_TIMEOUT,
    AsyncReceiptStreamProcessor,
)

HEARTBEAT = ": heartbeat\n\n"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse(raw: str) -> dict:
    """SSE chunk -> payload dict. Heartbeat comments -> {}."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def drain(gen):
    """All parsed data events, heartbeats dropped."""
    return [e for e in (parse(raw) for raw in gen if raw) if e]


def statuses(events):
    return [e.get("status") for e in events]


@pytest.fixture
def stub_worker(monkeypatch):
    """Replace receipt_worker_async with a controllable coroutine.

    Returns a control object:
        .delay          - seconds each worker sleeps before returning
        .fail_for       - identifiers that should come back as failures
        .raise_for      - identifiers whose worker raises
        .started        - threading.Event set on first worker entry
        .release        - threading.Event workers wait on, if set_gate() used
        .calls          - identifiers seen, in start order
    """
    import asyncio

    class Control:
        def __init__(self):
            self.delay = 0.0
            self.fail_for = set()
            self.raise_for = set()
            self.calls = []
            self.started = threading.Event()
            self.finished = threading.Event()
            self._gate = None

        def set_gate(self):
            self._gate = threading.Event()
            return self._gate

        async def worker(self, task, upload_folder, extractor, repository):
            self.calls.append(task.identifier)
            self.started.set()
            if self._gate is not None:
                while not self._gate.is_set():
                    await asyncio.sleep(0.01)
            if self.delay:
                await asyncio.sleep(self.delay)
            if task.identifier in self.raise_for:
                raise RuntimeError("worker exploded")
            self.finished.set()
            if task.identifier in self.fail_for:
                return ProcessingResult(
                    index=task.index, identifier=task.identifier,
                    success=False, error="extraction failed",
                )
            return ProcessingResult(
                index=task.index, identifier=task.identifier, success=True,
                data={"receipt_id": 100 + task.index, "receipt_status": "pending"},
            )

    control = Control()
    monkeypatch.setattr(processor_module, "receipt_worker_async", control.worker)
    monkeypatch.setattr(processor_module, "create_extractor",
                        lambda kind, cfg: object())
    monkeypatch.setattr(processor_module, "ReceiptRepository", lambda: object())
    return control


@pytest.fixture
def make_processor(app_with_db, tmp_path):
    """Build a processor inside an app context, with fast timeouts."""
    def _make(**kwargs):
        kwargs.setdefault("max_concurrency", 2)
        kwargs.setdefault("task_timeout", 5)
        kwargs.setdefault("stream_timeout", 10)
        kwargs.setdefault("heartbeat_interval", 0.05)
        with app_with_db.app_context():
            return AsyncReceiptStreamProcessor(upload_folder=str(tmp_path), **kwargs)
    return _make


def files(count=2):
    return [(f"file_{i}.jpg", f"/tmp/file_{i}.jpg") for i in range(count)]


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
class TestConfiguration:

    def test_explicit_arguments_win(self, make_processor):
        processor = make_processor(
            max_concurrency=7, task_timeout=1.5, stream_timeout=2.5,
            heartbeat_interval=3.5,
        )
        assert processor.max_concurrency == 7
        assert processor.task_timeout == 1.5
        assert processor.stream_timeout == 2.5
        assert processor.heartbeat_interval == 3.5

    def test_falls_back_to_app_config(self, app_with_db, tmp_path):
        app_with_db.config.update(
            GEMINI_MAX_CONCURRENCY=9,
            RECEIPT_TASK_TIMEOUT=11,
            RECEIPT_STREAM_TIMEOUT=22,
            RECEIPT_STREAM_HEARTBEAT=3,
        )
        with app_with_db.app_context():
            processor = AsyncReceiptStreamProcessor(upload_folder=str(tmp_path))
        assert processor.max_concurrency == 9
        assert processor.task_timeout == 11.0
        assert processor.stream_timeout == 22.0
        assert processor.heartbeat_interval == 3.0

    def test_falls_back_to_module_defaults(self, app_with_db, tmp_path):
        for key in ("GEMINI_MAX_CONCURRENCY", "RECEIPT_TASK_TIMEOUT",
                    "RECEIPT_STREAM_TIMEOUT", "RECEIPT_STREAM_HEARTBEAT"):
            app_with_db.config.pop(key, None)
        with app_with_db.app_context():
            processor = AsyncReceiptStreamProcessor(upload_folder=str(tmp_path))
        assert processor.max_concurrency == DEFAULT_MAX_CONCURRENCY
        assert processor.task_timeout == DEFAULT_TASK_TIMEOUT
        assert processor.stream_timeout == DEFAULT_STREAM_TIMEOUT
        assert processor.heartbeat_interval == DEFAULT_HEARTBEAT

    def test_numeric_types_are_coerced(self, app_with_db, tmp_path):
        """Env vars arrive as strings if the config layer doesn't cast them."""
        app_with_db.config.update(
            GEMINI_MAX_CONCURRENCY="3", RECEIPT_TASK_TIMEOUT="4",
        )
        with app_with_db.app_context():
            processor = AsyncReceiptStreamProcessor(upload_folder=str(tmp_path))
        assert processor.max_concurrency == 3
        assert processor.task_timeout == 4.0

    def test_captures_the_app_object_at_construction(self, make_processor,
                                                     app_with_db):
        """The generator body and worker thread both run outside the request
        context, so current_app must be resolved eagerly."""
        processor = make_processor()
        assert processor.app is app_with_db

    def test_requires_an_app_context(self, tmp_path):
        with pytest.raises(RuntimeError):
            AsyncReceiptStreamProcessor(upload_folder=str(tmp_path))


# --------------------------------------------------------------------------- #
# happy path / event protocol
# --------------------------------------------------------------------------- #
class TestEventProtocol:

    def test_event_sequence(self, make_processor, stub_worker):
        events = drain(make_processor().process_files(files(2)))
        assert statuses(events)[0] == "starting"
        assert statuses(events)[1:3] == ["processing", "processing"]
        assert statuses(events)[-1] == "completed"

    def test_one_queued_and_one_result_per_file(self, make_processor, stub_worker):
        events = drain(make_processor().process_files(files(3)))
        assert statuses(events).count("processing") == 3
        assert statuses(events).count("success") == 3

    def test_starting_event_reports_concurrency(self, make_processor, stub_worker):
        events = drain(make_processor(max_concurrency=5).process_files(files(1)))
        assert events[0]["total_files"] == 1
        assert events[0]["workers"] == 5

    def test_success_payload_is_passed_through(self, make_processor, stub_worker):
        events = drain(make_processor().process_files(files(1)))
        success = next(e for e in events if e["status"] == "success")
        assert success["receipt_id"] == 100
        assert success["receipt_status"] == "pending"
        assert success["filename"] == "file_0.jpg"

    def test_worker_failure_becomes_an_error_event(self, make_processor,
                                                   stub_worker):
        stub_worker.fail_for = {"file_0.jpg"}
        events = drain(make_processor().process_files(files(2)))
        error = next(e for e in events if e["status"] == "error")
        assert error["filename"] == "file_0.jpg"
        assert error["error"] == "extraction failed"
        assert statuses(events).count("success") == 1

    def test_worker_exception_becomes_an_error_event(self, make_processor,
                                                     stub_worker):
        stub_worker.raise_for = {"file_0.jpg"}
        events = drain(make_processor().process_files(files(1)))
        error = next(e for e in events if e["status"] == "error")
        assert "worker exploded" in error["error"]
        assert statuses(events)[-1] == "completed"

    def test_completed_event_tallies(self, make_processor, stub_worker):
        stub_worker.fail_for = {"file_1.jpg"}
        events = drain(make_processor().process_files(files(3)))
        completed = events[-1]
        assert completed["total_processed"] == 3
        assert completed["successes"] == 2
        assert completed["errors"] == 1

    def test_empty_file_list(self, make_processor, stub_worker):
        events = drain(make_processor().process_files([]))
        assert statuses(events) == ["starting", "completed"]
        assert events[-1]["total_processed"] == 0

    def test_worker_receives_the_upload_folder(self, make_processor, stub_worker,
                                               tmp_path, monkeypatch):
        seen = {}

        async def spy(task, upload_folder, extractor, repository):
            seen["folder"] = upload_folder
            return ProcessingResult(task.index, task.identifier, True, data={})

        monkeypatch.setattr(processor_module, "receipt_worker_async", spy)
        drain(make_processor().process_files(files(1)))
        assert seen["folder"] == str(tmp_path)

    def test_is_lazy(self, make_processor, stub_worker):
        """Building the generator must not start the worker thread."""
        make_processor().process_files(files(1))
        time.sleep(0.05)
        assert stub_worker.calls == []


# --------------------------------------------------------------------------- #
# concurrency
# --------------------------------------------------------------------------- #
class TestConcurrency:

    def test_all_files_are_processed_when_over_the_limit(self, make_processor,
                                                         stub_worker):
        events = drain(make_processor(max_concurrency=2).process_files(files(5)))
        assert statuses(events).count("success") == 5
        assert sorted(stub_worker.calls) == sorted(f for f, _ in files(5))

    def test_semaphore_bounds_in_flight_work(self, make_processor, monkeypatch):
        """No more than max_concurrency workers run at once."""
        import asyncio

        state = {"current": 0, "peak": 0}
        lock = threading.Lock()

        async def counting_worker(task, upload_folder, extractor, repository):
            with lock:
                state["current"] += 1
                state["peak"] = max(state["peak"], state["current"])
            await asyncio.sleep(0.05)
            with lock:
                state["current"] -= 1
            return ProcessingResult(task.index, task.identifier, True, data={})

        monkeypatch.setattr(processor_module, "receipt_worker_async",
                            counting_worker)
        monkeypatch.setattr(processor_module, "create_extractor",
                            lambda kind, cfg: object())
        monkeypatch.setattr(processor_module, "ReceiptRepository", lambda: object())

        drain(make_processor(max_concurrency=2).process_files(files(6)))
        assert state["peak"] <= 2

    def test_queued_events_precede_any_result(self, make_processor, stub_worker):
        stub_worker.delay = 0.02
        kinds = statuses(drain(make_processor().process_files(files(3))))
        first_result = min(i for i, k in enumerate(kinds) if k == "success")
        last_queued = max(i for i, k in enumerate(kinds) if k == "processing")
        assert last_queued < first_result


# --------------------------------------------------------------------------- #
# per-task timeout
# --------------------------------------------------------------------------- #
class TestTaskTimeout:

    def test_slow_task_is_reported_as_a_timeout(self, make_processor, stub_worker):
        stub_worker.delay = 5
        events = drain(
            make_processor(task_timeout=0.05, stream_timeout=10)
            .process_files(files(1))
        )
        error = next(e for e in events if e["status"] == "error")
        assert "Timed out after" in error["error"]
        assert error["filename"] == "file_0.jpg"

    def test_timeout_does_not_end_the_stream(self, make_processor, stub_worker,
                                             monkeypatch):
        """One slow file must not stop the others being reported."""
        import asyncio

        async def slow_for_first(task, upload_folder, extractor, repository):
            if task.index == 0:
                await asyncio.sleep(5)
            return ProcessingResult(task.index, task.identifier, True, data={})

        monkeypatch.setattr(processor_module, "receipt_worker_async",
                            slow_for_first)
        events = drain(
            make_processor(task_timeout=0.05, stream_timeout=10, max_concurrency=2)
            .process_files(files(2))
        )
        assert statuses(events).count("error") == 1
        assert statuses(events).count("success") == 1
        assert statuses(events)[-1] == "completed"

    def test_timeout_counts_towards_errors(self, make_processor, stub_worker):
        stub_worker.delay = 5
        events = drain(
            make_processor(task_timeout=0.05, stream_timeout=10)
            .process_files(files(1))
        )
        assert events[-1]["errors"] == 1


# --------------------------------------------------------------------------- #
# stream timeout / abort
# --------------------------------------------------------------------------- #
class TestStreamTimeout:

    @pytest.fixture
    def timed_out(self, make_processor, stub_worker):
        stub_worker.delay = 10
        return drain(
            make_processor(task_timeout=10, stream_timeout=0.15,
                           heartbeat_interval=0.05)
            .process_files(files(2))
        )

    def test_emits_a_fatal_event(self, timed_out):
        fatal = [e for e in timed_out if e.get("fatal")]
        assert len(fatal) == 1
        assert "was cancelled" in fatal[0]["error"]

    def test_every_pending_file_gets_a_cancelled_error(self, timed_out):
        cancelled = [e for e in timed_out if e.get("cancelled") is True]
        assert {e["filename"] for e in cancelled} == {"file_0.jpg", "file_1.jpg"}
        assert all("Cancelled:" in e["error"] for e in cancelled)

    def test_stream_ends_after_the_abort(self, timed_out):
        assert timed_out[-1].get("fatal") is True
        assert "completed" not in statuses(timed_out)

    def test_fatal_event_carries_the_tally(self, timed_out):
        fatal = next(e for e in timed_out if e.get("fatal"))
        assert fatal["total_files"] == 2
        assert fatal["cancelled"] == 2
        assert fatal["errors"] == 2

    def test_already_finished_files_are_not_cancelled(self, make_processor,
                                                      monkeypatch):
        """A file that completed before the deadline keeps its success event."""
        import asyncio

        async def fast_then_slow(task, upload_folder, extractor, repository):
            if task.index == 1:
                await asyncio.sleep(10)
            return ProcessingResult(task.index, task.identifier, True, data={})

        monkeypatch.setattr(processor_module, "receipt_worker_async",
                            fast_then_slow)
        monkeypatch.setattr(processor_module, "create_extractor",
                            lambda kind, cfg: object())
        monkeypatch.setattr(processor_module, "ReceiptRepository", lambda: object())

        events = drain(
            make_processor(task_timeout=10, stream_timeout=0.2,
                           heartbeat_interval=0.05, max_concurrency=2)
            .process_files(files(2))
        )
        assert any(e["status"] == "success" and e["filename"] == "file_0.jpg"
                   for e in events)
        # note: the fatal event also carries a `cancelled` key (a count),
        # so match on the per-file flag being exactly True
        cancelled = [e for e in events if e.get("cancelled") is True]
        assert [e["filename"] for e in cancelled] == ["file_1.jpg"]

    def test_worker_thread_is_cancelled(self, make_processor, stub_worker):
        stub_worker.delay = 10
        before = threading.active_count()
        drain(make_processor(task_timeout=10, stream_timeout=0.15,
                             heartbeat_interval=0.05).process_files(files(1)))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not any(t.name == "receipt-stream" and t.is_alive()
                       for t in threading.enumerate()):
                break
            time.sleep(0.05)
        assert not any(t.name == "receipt-stream" and t.is_alive()
                       for t in threading.enumerate())
        assert threading.active_count() <= before


# --------------------------------------------------------------------------- #
# heartbeats
# --------------------------------------------------------------------------- #
class TestHeartbeat:

    def test_heartbeats_are_emitted_while_idle(self, make_processor, stub_worker):
        gate = stub_worker.set_gate()
        stream = make_processor(heartbeat_interval=0.05, task_timeout=10,
                                stream_timeout=10).process_files(files(1))
        raw = []
        try:
            for chunk in stream:
                raw.append(chunk)
                if raw.count(HEARTBEAT) >= 2:
                    break
        finally:
            gate.set()
            stream.close()
        assert raw.count(HEARTBEAT) >= 2

    def test_heartbeat_is_an_sse_comment(self):
        """Clients must ignore it, so it carries no data: line."""
        assert HEARTBEAT.startswith(":")
        assert parse(HEARTBEAT) == {}

    def test_no_heartbeats_when_work_is_fast(self, make_processor, stub_worker):
        raw = list(make_processor(heartbeat_interval=5).process_files(files(1)))
        assert HEARTBEAT not in raw


# --------------------------------------------------------------------------- #
# failure of the machinery itself
# --------------------------------------------------------------------------- #
class TestThreadFailure:

    def test_setup_crash_is_reported_as_fatal(self, make_processor, monkeypatch):
        """create_extractor raising happens inside the thread, before any event."""
        def boom(kind, cfg):
            raise RuntimeError("no API key")

        monkeypatch.setattr(processor_module, "create_extractor", boom)
        monkeypatch.setattr(processor_module, "ReceiptRepository", lambda: object())

        events = drain(make_processor().process_files(files(1)))
        fatal = [e for e in events if e.get("fatal")]
        assert len(fatal) == 1
        assert "no API key" in fatal[0]["error"]

    def test_repository_construction_failure_is_reported(self, make_processor,
                                                         monkeypatch):
        def boom():
            raise RuntimeError("db gone")

        monkeypatch.setattr(processor_module, "create_extractor",
                            lambda kind, cfg: object())
        monkeypatch.setattr(processor_module, "ReceiptRepository", boom)

        events = drain(make_processor().process_files(files(1)))
        assert any("db gone" in e.get("error", "") for e in events if e.get("fatal"))

    def test_stream_terminates_after_a_crash(self, make_processor, monkeypatch):
        monkeypatch.setattr(processor_module, "create_extractor",
                            lambda kind, cfg: (_ for _ in ()).throw(
                                RuntimeError("boom")))
        monkeypatch.setattr(processor_module, "ReceiptRepository", lambda: object())
        events = drain(make_processor(stream_timeout=10).process_files(files(1)))
        assert events[-1].get("fatal") is True


# --------------------------------------------------------------------------- #
# client disconnect
# --------------------------------------------------------------------------- #
class TestClientDisconnect:

    def test_closing_the_generator_cancels_the_worker(self, make_processor,
                                                      stub_worker):
        stub_worker.delay = 10
        stream = make_processor(task_timeout=10, stream_timeout=10,
                                heartbeat_interval=0.05).process_files(files(2))
        next(stream)  # starting
        assert stub_worker.started.wait(timeout=5)
        stream.close()

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not any(t.name == "receipt-stream" and t.is_alive()
                       for t in threading.enumerate()):
                break
            time.sleep(0.05)
        assert not any(t.name == "receipt-stream" and t.is_alive()
                       for t in threading.enumerate())

    def test_close_is_safe_before_any_work_starts(self, make_processor,
                                                  stub_worker):
        stream = make_processor().process_files(files(1))
        stream.close()  # never iterated
        assert stub_worker.calls == []

    def test_close_midway_does_not_raise(self, make_processor, stub_worker):
        stub_worker.delay = 0.01
        stream = make_processor().process_files(files(3))
        next(stream)
        next(stream)
        stream.close()