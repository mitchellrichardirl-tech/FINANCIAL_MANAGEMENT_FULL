import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple
from datetime import datetime

from src.api.utils.sse import SSEEventBuilder, ProgressInfo

logger = logging.getLogger(__name__)


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
        return max_workers
    return min(cpu_limit, multiprocessing.cpu_count())


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
    
    def process(
        self,
        tasks: List[ProcessingTask],
        extra_worker_args: Tuple = ()
    ) -> Generator[str, None, None]:
        """
        Process tasks in parallel and yield SSE events.
        
        Args:
            tasks: List of ProcessingTask objects
            extra_worker_args: Additional arguments to pass to worker function
            
        Yields:
            SSE-formatted event strings
        """
        total = len(tasks)
        processed_count = 0
        
        # Starting event
        yield SSEEventBuilder.starting(total, workers=self.max_workers)
        
        # Prepare worker arguments
        worker_args = [
            (task.index, task.identifier, task.data, *extra_worker_args)
            for task in tasks
        ]
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks and emit queued events
            future_to_task = {}
            for task, args in zip(tasks, worker_args):
                yield SSEEventBuilder.processing(
                    index=task.index,
                    identifier=task.identifier,
                    progress=ProgressInfo(processed_count, total),
                    message="Queued for processing..."
                )
                
                future = executor.submit(self.worker_function, args)
                future_to_task[future] = task
            
            # Process results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                
                try:
                    result: ProcessingResult = future.result()
                    processed_count += 1
                    progress = ProgressInfo(processed_count, total)
                    
                    if result.success:
                        yield SSEEventBuilder.success(
                            index=result.index,
                            identifier=result.identifier,
                            result_data=result.data or {},
                            progress=progress
                        )
                    else:
                        yield SSEEventBuilder.error(
                            index=result.index,
                            identifier=result.identifier,
                            error_message=result.error or "Unknown error",
                            progress=progress
                        )
                        
                except Exception as e:
                    processed_count += 1
                    logger.error(f"Worker error for {task.identifier}: {e}")
                    
                    yield SSEEventBuilder.error(
                        index=task.index,
                        identifier=task.identifier,
                        error_message=f"Processing failed: {str(e)}",
                        progress=ProgressInfo(processed_count, total)
                    )
        
        # Completion event
        yield SSEEventBuilder.completed(processed_count)