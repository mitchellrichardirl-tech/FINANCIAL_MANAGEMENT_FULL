import asyncio
import logging
import queue
import threading
import time
from contextlib import aclosing
from typing import Optional

from flask import current_app

from src.api.models.processing import ProcessingTask
from src.api.services.receipt_processor import receipt_worker_async
from src.api.utils.stream_reporter import StreamEventReporter
from src.database.repositories.receipts import ReceiptRepository
from src.receipts.extractor_factory import create_extractor

logger = logging.getLogger(__name__)
_EVENT = "event"
_ERROR = "error"
_DONE = "done"
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_TASK_TIMEOUT = 180  # seconds per file (after acquiring the semaphore)
DEFAULT_STREAM_TIMEOUT = 900  # seconds for the whole request
DEFAULT_HEARTBEAT = 10  # seconds between keep-alive events when idle


class AsyncReceiptStreamProcessor:
    def __init__(
        self,
        upload_folder,
        allowed_extensions=None,
        max_concurrency: Optional[int] = None,
        extractor_config=None,
        task_timeout: Optional[float] = None,
        stream_timeout: Optional[float] = None,
        heartbeat_interval: Optional[float] = None,
    ):
        # Capture the real app object now, while we're still in the request
        # context. The generator body runs later and the worker runs in
        # another thread, so neither can rely on `current_app`.
        self.app = current_app._get_current_object()
        cfg = self.app.config
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        self.extractor_config = extractor_config or {}
        self.max_concurrency = int(
            max_concurrency
            or cfg.get("GEMINI_MAX_CONCURRENCY")
            or DEFAULT_MAX_CONCURRENCY
        )
        self.task_timeout = float(
            task_timeout or cfg.get("RECEIPT_TASK_TIMEOUT", DEFAULT_TASK_TIMEOUT)
        )
        self.stream_timeout = float(
            stream_timeout or cfg.get("RECEIPT_STREAM_TIMEOUT", DEFAULT_STREAM_TIMEOUT)
        )
        self.heartbeat_interval = float(
            heartbeat_interval or cfg.get("RECEIPT_STREAM_HEARTBEAT", DEFAULT_HEARTBEAT)
        )

    # ------------------------------------------------------------------ #
    # Async side: runs inside the background thread's event loop
    # ------------------------------------------------------------------ #
    async def _aprocess(self, tasks, reporter):
        yield reporter.starting(workers=self.max_concurrency)
        extractor = create_extractor("multimodal", self.extractor_config)
        repository = ReceiptRepository()
        sem = asyncio.Semaphore(self.max_concurrency)

        async def bounded(task):
            """Always returns an event. Never raises, except CancelledError."""
            async with sem:
                try:
                    result = await asyncio.wait_for(
                        receipt_worker_async(task, self.upload_folder, extractor, repository),
                        timeout=self.task_timeout,
                    )
                    return reporter.result(result)
                except TimeoutError:
                    return reporter.failed(
                        task, f"Timed out after {self.task_timeout:.0f}s"
                    )
                except Exception as exc:
                    logger.exception(
                        "[AsyncReceiptStreamProcessor.bounded] Task %s crashed: %s",
                        task.index, task.identifier,
                    )
                    return reporter.exception(task, exc)

        futures = []
        try:
            for task in tasks:
                yield reporter.queued(task)
                futures.append(asyncio.create_task(bounded(task)))
            for fut in asyncio.as_completed(futures):
                yield await fut
            yield reporter.completed()
        finally:
            # Runs on normal exit, error, or cancellation.
            for fut in futures:
                fut.cancel()

    # ------------------------------------------------------------------ #
    # Sync side: the WSGI generator Flask iterates
    # ------------------------------------------------------------------ #
    def process_files(self, temp_files, form_data=None):
        tasks = [ProcessingTask(i, fn, tp) for i, (fn, tp) in enumerate(temp_files)]
        reporter = StreamEventReporter(total=len(tasks))
        q: queue.Queue = queue.Queue()
        stop = threading.Event()
        loop_ref: dict = {}

        async def runner():
            loop_ref["loop"] = asyncio.get_running_loop()
            loop_ref["task"] = asyncio.current_task()
            if stop.is_set():  # cancelled before we even started
                return
            async with aclosing(self._aprocess(tasks, reporter)) as events:
                async for event in events:
                    q.put((_EVENT, event))

        def thread_main():
            try:
                with self.app.app_context():
                    asyncio.run(runner())
            except asyncio.CancelledError:
                logger.info(
                    "[AsyncReceiptStreamProcessor.thread_main] Processing cancelled"
                )
            except BaseException as exc:
                logger.exception(
                    "[AsyncReceiptStreamProcessor.thread_main] Processing failed"
                )
                q.put((_ERROR, exc))
            finally:
                q.put((_DONE, None))  # always sent, whatever happened above

        def cancel():
            stop.set()
            loop, task = loop_ref.get("loop"), loop_ref.get("task")
            if loop is not None and task is not None:
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass  # loop already closed, nothing left to cancel

        thread = threading.Thread(
            target=thread_main, name="receipt-stream", daemon=True
        )
        thread.start()
        deadline = time.monotonic() + self.stream_timeout
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    yield from reporter.abort(
                        f"Processing exceeded {self.stream_timeout:.0f}s and was cancelled"
                    )
                    break
                try:
                    kind, payload = q.get(timeout=min(self.heartbeat_interval, remaining))
                except queue.Empty:
                    if not thread.is_alive() and q.empty():
                        yield from reporter.abort("Processing stopped unexpectedly")
                        break
                    yield reporter.heartbeat()
                    continue
                if kind == _DONE:
                    break
                if kind == _ERROR:
                    yield from reporter.abort(f"Processing failed: {payload}")
                    continue          # _DONE follows
                if payload:           # result() returns "" for late results after abort
                    yield payload
        finally:
            # Covers normal exit, timeout, client disconnect (GeneratorExit),
            # and gunicorn abort (SystemExit).
            cancel()
            thread.join(timeout=5)
            if thread.is_alive():
                logger.info(
                    "[AsyncReceiptStreamProcessor.process_files] Worker thread still "
                    "finishing in-flight calls after cancel; it will exit when they return"
                )
