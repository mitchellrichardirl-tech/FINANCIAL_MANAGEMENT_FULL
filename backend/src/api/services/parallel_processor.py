import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from src.api.utils.sse import SSEEventBuilder, ProgressInfo
from src.api.utils.stream_reporter import StreamEventReporter

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


@dataclass
class ProcessingTask:
   """Represents a single processing task."""
   index: int
   identifier: str
   data: Any  # Task-specific data


@dataclass
class ProcessingResult:
   """Result from processing a single task."""
   index: int
   identifier: str
   success: bool
   data: Optional[Dict[str, Any]] = None
   error: Optional[str] = None


def get_optimal_workers(max_workers: Optional[int] = None, cpu_limit: int = 4) -> int:
   """Calculate optimal number of workers."""
   if max_workers is not None:
       logger.debug(f"Using specified max_workers: {max_workers}")
       return max_workers

   cpu_count = multiprocessing.cpu_count()
   optimal = min(cpu_limit, cpu_count)
   logger.debug(f"Calculated optimal workers: {optimal} (cpu_count={cpu_count}, limit={cpu_limit})")
   return optimal


class ParallelStreamProcessor:
    """
    Generic parallel processor with SSE streaming support.
    
    This class handles the complexity of multiprocessing while providing
    a simple interface for streaming results.
    """

    def __init__(
        self,
        worker_function: Callable[[Tuple], ProcessingResult],
        max_workers: Optional[int] = None
    ):
        self.worker_function = worker_function
        self.max_workers = get_optimal_workers(max_workers)
        logger.debug(
            f"Initialized processor with worker={worker_function.__name__}, "
            f"max_workers={self.max_workers}"
        )

    def process(self, tasks, extra_worker_args=()):
        reporter = StreamEventReporter(total=len(tasks))
        yield reporter.starting(workers=self.max_workers)
        worker_args = [(t.index, t.identifier, t.data, *extra_worker_args) for t in tasks]
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for task, args in zip(tasks, worker_args):
                yield reporter.queued(task)
                future_to_task[executor.submit(self.worker_function, args)] = task
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                yield reporter.result(future.result())
            except Exception as e:
                logger.error(f"Worker exception for task {task.index} ({task.identifier}): {e}")
                yield reporter.exception(task, e)
        yield reporter.completed()