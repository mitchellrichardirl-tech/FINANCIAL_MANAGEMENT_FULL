import numpy as np
from dataclasses import dataclass
from typing import Dict
from datetime import datetime
from pathlib import Path

@dataclass
class Receipt:
    source_file: Path
    page_number: int
    original_image: np.ndarray
    processed_images: Dict[str, np.ndarray]
    extracted_texts: Dict[str, str] | None = None
    selected_method: str | None = None
    confidence: float | None = None
    vendor: str | None = None
    date: datetime | None = None
    amount: float | None = None