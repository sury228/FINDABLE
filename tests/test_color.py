"""Unit tests for color science formulas, von Kries balancing, and ΔE metrics."""

import numpy as np
import pytest

from app.color.metrics import (
    calculate_ita,
    calculate_match_score,
    depth_from_ita,
    undertone_from_hue,
)
from app.color.pipeline import (
    delta_e,
    linear_to_srgb,
    srgb_to_linear,
    white_balance,
)


def test_srgb_linear_roundtrip():
    """Verify sRGB -> linear -> sRGB inversion accuracy."""
    original = np.array([0.0, 64.0, 128.0, 200.0, 255.0])
    lin = srgb_to_linear(original)
    reconstructed = linear_to_srgb(lin) * 255.0
    assert np.allclose(original, reconstructed, atol=1e-3)


def test_delta_e_identical():
    """Delta E of identical colors must be zero."""
    lab = [60.0, 15.0, 25.0]
    dist = delta_e(lab, lab)
    assert pytest.approx(dist, abs=1e-4) == 0.0


def test_delta_e_distance():
    """Delta E of distinguishable colors should be positive and bounded."""
    lab1 = [62.4, 13.9, 24.1]
    lab2 = [60.0, 14.5, 23.0]
    dist = delta_e(lab1, lab2)
    assert 1.0 <= dist <= 3.0


def test_ita_calculation_and_depth():
    """Verify Individual Typology Angle calculation and depth classification."""
    # Light skin: high L*, moderate b*
    ita_light = calculate_ita(L=82.0, b=16.0)
    assert ita_light > 41.0
    assert depth_from_ita(ita_light) in ("light", "very light")

    # Tan skin
    ita_tan = calculate_ita(L=62.0, b=24.0)
    assert depth_from_ita(ita_tan) == "tan"

    # Deep skin
    ita_deep = calculate_ita(L=42.0, b=22.0)
    assert depth_from_ita(ita_deep) == "deep"


def test_undertone_classification():
    """Verify undertone classification based on hue angle."""
    assert undertone_from_hue(65.0) == "warm"
    assert undertone_from_hue(58.0) == "neutral"
    assert undertone_from_hue(48.0) == "cool"


def test_match_score_penalty():
    """Verify that match score applies appropriate undertone mismatch penalties."""
    score_same, label_same, _ = calculate_match_score(1.5, "warm", "warm")
    assert score_same == 1.5
    assert label_same == "match"

    score_opp, label_opp, _ = calculate_match_score(1.5, "warm", "cool")
    assert score_opp == 5.5  # 1.5 + 4.0 penalty
    assert label_opp == "close" or label_opp == "different"

