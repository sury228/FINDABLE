"""Color science and physical calibration pipeline package."""

from app.color.pipeline import (
    crop,
    delta_e,
    linear_to_srgb,
    srgb_to_linear,
    swatch_lab,
    white_balance,
)
from app.color.metrics import (
    calculate_ita,
    calculate_match_score,
    compute_confidence,
    depth_from_ita,
    undertone_from_hue,
)

__all__ = [
    "crop",
    "delta_e",
    "linear_to_srgb",
    "srgb_to_linear",
    "swatch_lab",
    "white_balance",
    "calculate_ita",
    "calculate_match_score",
    "compute_confidence",
    "depth_from_ita",
    "undertone_from_hue",
]
