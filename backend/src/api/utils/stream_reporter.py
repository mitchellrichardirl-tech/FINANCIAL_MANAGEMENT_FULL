import asyncio

from src.api.utils.sse import SSEEventBuilder, ProgressInfo
from src.utils.logging import ContextLogger
logger = ContextLogger(__name__)


class StreamEventReporter:
    """
    Owns the SSE event protocol for batch processing:
    event sequence, progress counters, and logging.
    I/O-model agnostic -- usable from sync and async processors.
    """
    def __init__(self, total: int):
        self.total = total
        self.processed = 0
        self.successes = 0
        self.errors = 0

    def starting(self, **meta) -> str:
        logger.info(f"Starting processing: {self.total} tasks | {meta}")
        return SSEEventBuilder.starting(self.total, **meta)

    def queued(self, task: "ProcessingTask") -> str:
        logger.debug(f"Queuing task {task.index}: {task.identifier}")
        return SSEEventBuilder.processing(
            index=task.index,
            identifier=task.identifier,
            progress=ProgressInfo(self.processed, self.total),
            message="Queued for processing...",
        )

    def result(self, result: "ProcessingResult") -> str:
        self.processed += 1
        progress = ProgressInfo(self.processed, self.total)
        if result.success:
            self.successes += 1
            logger.debug(f"Task {result.index} succeeded: {result.identifier}")
            return SSEEventBuilder.success(
                index=result.index,
                identifier=result.identifier,
                result_data=result.data or {},
                progress=progress,
            )
        self.errors += 1
        logger.warning(f"Task {result.index} failed: {result.identifier} | {result.error}")
        return SSEEventBuilder.error(
            index=result.index,
            identifier=result.identifier,
            error_message=result.error or "Unknown error",
            progress=progress,
        )

    def exception(self, task: "ProcessingTask", exc: Exception) -> str:
        """For failures that escape the worker entirely."""
        return self.result(ProcessingResult(
            index=task.index,
            identifier=task.identifier,
            success=False,
            error=f"Processing failed: {exc}",
        ))

    def completed(self) -> str:
        logger.info(
            f"Processing complete: {self.processed}/{self.total} | "
            f"success={self.successes} | errors={self.errors}"
        )
        return SSEEventBuilder.completed(self.processed)