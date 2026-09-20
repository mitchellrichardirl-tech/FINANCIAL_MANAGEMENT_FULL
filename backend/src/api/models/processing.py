"""Shared data types for batch processing.
Deliberately dependency-free so any layer can import it without cycles.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
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