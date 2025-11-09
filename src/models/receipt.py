import numpy as np
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class Receipt:
    source_file: Path
    page_number: int
    original_image: np.ndarray
    processed_image: np.ndarray
    vendor: str | None = None
    date: datetime | None = None
    amount: float | None = None