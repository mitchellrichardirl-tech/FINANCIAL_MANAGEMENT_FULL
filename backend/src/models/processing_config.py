"""
Configuration model for receipt image pre-processing.

Defines the tunable parameters used by the image processing pipeline
when preparing receipt photos for OCR extraction. Default values are
tuned for typical receipt images (white/off-white paper, variable
lighting, phone-camera quality).
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ProcessingConfig:
    """Parameters controlling the image pre-processing pipeline.

    Passed to the image processor to control resizing, denoising,
    contrast enhancement, and sharpening. All fields have sensible
    defaults; override individual values when a specific receipt source
    needs different treatment.

    Attributes:
        max_dimension: Maximum width or height in pixels. Images
            exceeding this are downscaled proportionally. Keeps OCR
            processing time bounded.
        denoise_filter_size: Kernel size for the median denoising
            filter. Must be odd. Larger values remove more noise but
            blur fine text.
        contrast_factor: Multiplier for PIL contrast enhancement.
            1.0 = no change, >1.0 = increased contrast.
        sharpness_factor: Multiplier for PIL sharpness enhancement.
            1.0 = no change, >1.0 = sharper.
        clahe_clip_limit: Clip limit for Contrast Limited Adaptive
            Histogram Equalization (CLAHE). Higher values allow more
            contrast amplification but may increase noise.
        clahe_tile_size: Grid size (rows, cols) for CLAHE. Smaller
            tiles adapt to more local contrast variations.
        bilateral_d: Diameter of the pixel neighbourhood for the
            bilateral filter. Larger values consider more distant
            pixels.
        bilateral_sigma_color: Bilateral filter sigma in colour space.
            Larger values blend more dissimilar colours.
        bilateral_sigma_space: Bilateral filter sigma in coordinate
            space. Larger values blend more distant pixels.
    """
    max_dimension: int = 1500
    denoise_filter_size: int = 3
    contrast_factor: float = 2.0
    sharpness_factor: float = 1.5
    clahe_clip_limit: float = 2.0
    clahe_tile_size: Tuple[int, int] = (8, 8)
    bilateral_d: int = 9
    bilateral_sigma_color: int = 75
    bilateral_sigma_space: int = 75