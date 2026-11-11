"""Color calibration, von Kries white balancing, and CIELAB extraction."""

from typing import List, Sequence, Tuple
import numpy as np
from skimage import color


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    """Convert sRGB array in range [0, 255] to linear RGB in range [0, 1]."""
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    """Convert linear RGB in range [0, 1] back to sRGB in range [0, 1]."""
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def crop(img: np.ndarray, box: Sequence[int]) -> np.ndarray:
    """Crop image with box coordinates [x0, y0, x1, y1]."""
    x0, y0, x1, y1 = box
    return img[y0:y1, x0:x1]


def white_balance(img_rgb: np.ndarray, paper_box: Sequence[int], target: float = 0.85) -> np.ndarray:
    """Perform von Kries white balance against paper reference box in linear RGB.

    Target 0.85 in linear RGB corresponds to approximately L* 94.
    """
    lin = srgb_to_linear(img_rgb.astype(np.float64))
    paper = crop(lin, paper_box).reshape(-1, 3)
    raw = crop(img_rgb, paper_box).reshape(-1, 3)

    # Discard specular clipped pixels (any channel >= 250)
    valid_mask = raw.max(axis=1) < 250
    if np.any(valid_mask):
        paper_clean = paper[valid_mask]
    else:
        paper_clean = paper

    paper_median = np.median(paper_clean, axis=0)
    # Guard against division by zero
    paper_median = np.where(paper_median == 0, 1e-5, paper_median)

    scale_factors = target / paper_median
    return lin * scale_factors


def swatch_lab(lin_img: np.ndarray, box: Sequence[int]) -> np.ndarray:
    """Sample swatch from inner 60% of bounding box, trim outliers, and return median [L*, a*, b*]."""
    x0, y0, x1, y1 = box
    dx = max(1, (x1 - x0) // 5)
    dy = max(1, (y1 - y0) // 5)

    patch_linear = lin_img[y0 + dy : y1 - dy, x0 + dx : x1 - dx]
    patch_srgb = linear_to_srgb(patch_linear)

    # Reshape and transform to CIELAB (D65)
    patch_reshaped = patch_srgb.reshape(-1, 1, 3)
    lab = color.rgb2lab(patch_reshaped).reshape(-1, 3)

    # Filter out darkest and brightest 10% by L* (glare / paper grain)
    lo, hi = np.percentile(lab[:, 0], [10, 90])
    inlier_mask = (lab[:, 0] >= lo) & (lab[:, 0] <= hi)
    if np.any(inlier_mask):
        lab = lab[inlier_mask]

    return np.median(lab, axis=0)


def delta_e(lab1: Sequence[float], lab2: Sequence[float]) -> float:
    """Calculate CIEDE2000 color difference between two CIELAB coordinates."""
    a1 = np.asarray(lab1, dtype=np.float64).reshape(1, 1, 3)
    a2 = np.asarray(lab2, dtype=np.float64).reshape(1, 1, 3)
    return float(color.deltaE_ciede2000(a1, a2)[0, 0])


def lab_to_hex(lab: Sequence[float]) -> str:
    """Convert CIELAB coordinate to standard sRGB hexadecimal representation."""
    lab_arr = np.asarray(lab, dtype=np.float64).reshape(1, 1, 3)
    rgb = color.lab2rgb(lab_arr)[0, 0]
    rgb_clipped = np.clip(rgb * 255.0, 0, 255).astype(int)
    return f"#{rgb_clipped[0]:02X}{rgb_clipped[1]:02X}{rgb_clipped[2]:02X}"


def rgb_to_lab(rgb: Sequence[float]) -> List[float]:
    """Convert sRGB array in range [0, 255] to CIELAB [L*, a*, b*]."""
    rgb_arr = np.asarray(rgb, dtype=np.float64).reshape(1, 1, 3) / 255.0
    lab = color.rgb2lab(rgb_arr)[0, 0]
    return [round(float(lab[0]), 2), round(float(lab[1]), 2), round(float(lab[2]), 2)]
