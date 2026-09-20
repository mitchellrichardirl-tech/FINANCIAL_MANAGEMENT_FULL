import threading
from typing import Dict, List

from src.api.models.processing import ProcessingResult, ProcessingTask
from src.api.utils.sse import ProgressInfo, SSEEventBuilder
from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class StreamEventReporter:
    """
    Owns the SSE event protocol for batch processing:
    event sequence, progress counters, and logging.
    I/O-model agnostic and thread-safe. The async processor calls queued() and
    result() from its event-loop thread, and abort() and heartbeat() from the
    request thread.
    """

    def __init__(self, total: int):
        self.total = total
        self.processed = 0
        self.successes = 0
        self.errors = 0
        self._pending: Dict[int, str] = {}  # index -> identifier
        self._aborted = False
        self._lock = threading.Lock()

    def _progress(self) -> ProgressInfo:
        """Call while holding self._lock."""
        return ProgressInfo(self.processed, self.total)

    # ---- lifecycle events -------------------------------------------------
    def starting(self, **meta) -> str:
        logger.info(f"Starting processing: {self.total} tasks | {meta}")
        return SSEEventBuilder.starting(self.total, **meta)

    def queued(self, task: ProcessingTask) -> str:
        with self._lock:
            self._pending[task.index] = task.identifier
            progress = self._progress()
        logger.debug(f"Queuing task {task.index}: {task.identifier}")
        return SSEEventBuilder.processing(
            index=task.index,
            identifier=task.identifier,
            progress=progress,
            message="Queued for processing...",
        )

    def result(self, result: ProcessingResult) -> str:
        with self._lock:
            if self._aborted:
                # abort() already reported this file. Don't count it twice.
                logger.debug(
                    f"Ignoring late result for task {result.index} after abort"
                )
                return ""
            self._pending.pop(result.index, None)
            self.processed += 1
            if result.success:
                self.successes += 1
            else:
                self.errors += 1
            progress = self._progress()
        if result.success:
            logger.debug(f"Task {result.index} succeeded: {result.identifier}")
            return SSEEventBuilder.success(
                index=result.index,
                identifier=result.identifier,
                result_data=result.data or {},
                progress=progress,
            )
        logger.warning(
            f"Task {result.index} failed: {result.identifier} | {result.error}"
        )
        return SSEEventBuilder.error(
            index=result.index,
            identifier=result.identifier,
            error_message=result.error or "Unknown error",
            progress=progress,
        )

    def failed(self, task: ProcessingTask, message: str) -> str:
        """A single file failed outside the worker (timeout, crash)."""
        return self.result(
            ProcessingResult(
                index=task.index,
                identifier=task.identifier,
                success=False,
                error=message,
            )
        )

    def exception(self, task: ProcessingTask, exc: Exception) -> str:
        """For failures that escape the worker entirely."""
        return self.failed(task, f"Processing failed: {exc}")

    def completed(self) -> str:
        with self._lock:
            processed, successes, errors = self.processed, self.successes, self.errors
        logger.info(
            f"Processing complete: {processed}/{self.total} | "
            f"success={successes} | errors={errors}"
        )
        return SSEEventBuilder.completed(processed, successes=successes, errors=errors)

    # ---- stream-level events ----------------------------------------------
    def abort(self, message: str) -> List[str]:
        """
        The whole stream is ending early. Emit a per-file error for every file
        the client saw queued but never got a result for, then a fatal event.
        Returns a list so the caller can `yield from` it: one SSE event per chunk.
        Idempotent: a second call returns [].
        """
        with self._lock:
            if self._aborted:
                return []
            self._aborted = True
            pending = sorted(self._pending.items())
            self._pending.clear()
            events = []
            for index, identifier in pending:
                self.processed += 1
                self.errors += 1
                events.append(
                    SSEEventBuilder.error(
                        index=index,
                        identifier=identifier,
                        error_message=f"Cancelled: {message}",
                        progress=self._progress(),
                        cancelled=True,
                    )
                )
            processed, successes, errors = self.processed, self.successes, self.errors
        logger.error(
            f"Processing aborted: {message} | {processed}/{self.total} | "
            f"success={successes} | errors={errors} | cancelled={len(pending)}"
        )
        events.append(
            SSEEventBuilder.fatal_error(
                error_message=message,
                total_processed=processed,
                total_files=self.total,
                successes=successes,
                errors=errors,
                cancelled=len(pending),
            )
        )
        return events

    def heartbeat(self) -> str:
        return SSEEventBuilder.heartbeat()
