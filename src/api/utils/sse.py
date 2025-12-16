import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar
from dataclasses import dataclass, asdict
from flask import Response

logger = logging.getLogger(__name__)

T = TypeVar('T')

@dataclass
class ProgressInfo:
    """Progress information for batch operations."""
    current: int
    total: int
    
    @property
    def percentage(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": self.current,
            "total": self.total,
            "percentage": self.percentage
        }


class SSEEventBuilder:
    """Builder for common SSE event types."""
    
    @staticmethod
    def _format_event(data: Dict[str, Any]) -> str:
        """Format data as SSE event string."""
        return f"data: {json.dumps(data)}\n\n"
    
    @classmethod
    def starting(cls, total_items: int, workers: int = 1, **extra) -> str:
        """Create a 'starting' event."""
        return cls._format_event({
            "status": "starting",
            "total_files": total_items,
            "workers": workers,
            "timestamp": datetime.now().isoformat(),
            **extra
        })
    
    @classmethod
    def processing(
        cls,
        index: int,
        identifier: str,
        progress: ProgressInfo,
        message: str = "Processing...",
        **extra
    ) -> str:
        """Create a 'processing' event."""
        return cls._format_event({
            "status": "processing",
            "file_index": index,
            "filename": identifier,
            "message": message,
            "progress": progress.to_dict(),
            "timestamp": datetime.now().isoformat(),
            **extra
        })
    
    @classmethod
    def success(
        cls,
        index: int,
        identifier: str,
        result_data: Dict[str, Any],
        progress: ProgressInfo,
        **extra
    ) -> str:
        """Create a 'success' event."""
        return cls._format_event({
            "status": "success",
            "file_index": index,
            "filename": identifier,
            "progress": progress.to_dict(),
            "timestamp": datetime.now().isoformat(),
            **result_data,
            **extra
        })
    
    @classmethod
    def error(
        cls,
        index: int,
        identifier: str,
        error_message: str,
        progress: Optional[ProgressInfo] = None,
        **extra
    ) -> str:
        """Create an 'error' event."""
        data = {
            "status": "error",
            "file_index": index,
            "filename": identifier,
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
            **extra
        }
        if progress:
            data["progress"] = progress.to_dict()
        return cls._format_event(data)
    
    @classmethod
    def completed(cls, total_processed: int, **extra) -> str:
        """Create a 'completed' event."""
        return cls._format_event({
            "status": "completed",
            "total_processed": total_processed,
            "message": "All receipts processed",
            "timestamp": datetime.now().isoformat(),
            **extra
        })
    
    @classmethod
    def fatal_error(cls, error_message: str, details: Optional[str] = None) -> str:
        """Create a fatal error event."""
        data = {
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        if details:
            data["details"] = details
        return cls._format_event(data)


def create_sse_response(
    generator: Generator[str, None, None],
    headers: Optional[Dict[str, str]] = None
) -> Response:
    """Create a Flask SSE response from a generator."""
    default_headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    if headers:
        default_headers.update(headers)
    
    return Response(
        generator,
        mimetype="text/event-stream",
        headers=default_headers
    )


def create_error_sse_response(
    error_message: str, 
    details: Optional[str] = None
) -> Response:
    """Create an SSE response for an error condition."""
    return create_sse_response(
        iter([SSEEventBuilder.fatal_error(error_message, details)])
    )


class BatchProcessor:
    """Generic batch processor with SSE streaming support."""
    
    def __init__(self, items: List[T], max_workers: int = 4):
        self.items = items
        self.max_workers = max_workers
        self.total = len(items)
        self.processed_count = 0
    
    def get_progress(self) -> ProgressInfo:
        """Get current progress info."""
        return ProgressInfo(current=self.processed_count, total=self.total)
    
    def increment_progress(self):
        """Increment the processed count."""
        self.processed_count += 1
    
    def process_sequential(
        self,
        processor: Callable[[int, T], Dict[str, Any]],
        get_identifier: Callable[[T], str]
    ) -> Generator[str, None, None]:
        """Process items sequentially with SSE events."""
        yield SSEEventBuilder.starting(self.total, workers=1)
        
        for index, item in enumerate(self.items):
            identifier = get_identifier(item)
            
            # Emit processing event
            yield SSEEventBuilder.processing(
                index=index,
                identifier=identifier,
                progress=self.get_progress(),
                message="Processing..."
            )
            
            try:
                result = processor(index, item)
                self.increment_progress()
                
                yield SSEEventBuilder.success(
                    index=index,
                    identifier=identifier,
                    result_data=result,
                    progress=self.get_progress()
                )
            except Exception as e:
                self.increment_progress()
                logger.error(f"Error processing {identifier}: {e}")
                
                yield SSEEventBuilder.error(
                    index=index,
                    identifier=identifier,
                    error_message=str(e),
                    progress=self.get_progress()
                )
        
        yield SSEEventBuilder.completed(self.processed_count)