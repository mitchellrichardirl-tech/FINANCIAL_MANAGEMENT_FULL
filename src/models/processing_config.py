from dataclasses import dataclass
from typing import Tuple

@dataclass
class ProcessingConfig:
    """Configuration for image processing."""
    max_dimension: int = 1500
    denoise_filter_size: int = 3
    contrast_factor: float = 2.0
    sharpness_factor: float = 1.5
    clahe_clip_limit: float = 2.0
    clahe_tile_size: Tuple[int, int] = (8, 8)
    bilateral_d: int = 9
    bilateral_sigma_color: int = 75
    bilateral_sigma_space: int = 75