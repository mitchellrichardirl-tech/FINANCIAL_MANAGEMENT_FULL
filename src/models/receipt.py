import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

@dataclass
class Receipt:
    original_filename: Path
    page_number: int
    original_image: np.ndarray | None = None
    processed_images: Dict[str, np.ndarray] | None = None
    extracted_text: str | None = None
    selected_method: str | None = None
    confidence: float | None = None
    vendor: str | None = None
    date: datetime | None = None
    amount: float | None = None
    stored_filename: str | None = None
    file_path: Path | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
