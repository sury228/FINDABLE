"""Derived color metrics: Individual Typology Angle (ITA), undertone, and match scoring."""

import math
from typing import Tuple


def calculate_ita(L: float, b: float) -> float:
    """Calculate Individual Typology Angle (ITA) in degrees.

    Formula: ITA = arctan((L* - 50) / b*) * (180 / pi)
    """
    if abs(b) < 1e-5:
        b = 1e-5 if b >= 0 else -1e-5
    ita_rad = math.atan((L - 50.0) / b)
    return float(math.degrees(ita_rad))


def depth_from_ita(ita_deg: float) -> str:
    """Classify skin depth bucket from Individual Typology Angle (ITA).

    - > 55: very light
    - 41 to 55: light
    - 28 to 41: medium
    - 10 to 28: tan
    - -30 to 10: deep
    - < -30: rich
    """
    if ita_deg > 55.0:
        return "very light"
    elif ita_deg > 41.0:
        return "light"
    elif ita_deg > 28.0:
        return "medium"
    elif ita_deg > 10.0:
        return "tan"
    elif ita_deg >= -30.0:
        return "deep"
    else:
        return "rich"


def undertone_from_hue(hue_deg: float) -> str:
    """Classify undertone from hue angle (in degrees).

    - h >= 62°: warm
    - 55° <= h < 62°: neutral
    - h < 55°: cool
    """
    normalized_hue = hue_deg % 360.0
    if normalized_hue >= 62.0:
        return "warm"
    elif normalized_hue >= 55.0:
        return "neutral"
    else:
        return "cool"


def compute_confidence(
    paper_l_spread: float = 1.0,
    swatch_glare_ratio: float = 0.0,
    swatch_l_spread: float = 2.0,
    raw_paper_l: float = 85.0,
) -> int:
    """Compute measurement confidence score (0 to 100) from physical photo quality indicators."""
    score = 100.0

    # Uneven paper penalty (spread above 3)
    if paper_l_spread > 3.0:
        score -= min(25.0, (paper_l_spread - 3.0) * 5.0)

    # Specular glare penalty
    if swatch_glare_ratio > 0.05:
        score -= min(30.0, swatch_glare_ratio * 200.0)

    # Patchy swatch penalty (spread above 6)
    if swatch_l_spread > 6.0:
        score -= min(20.0, (swatch_l_spread - 6.0) * 4.0)

    # Under-exposed penalty (paper L* below 60)
    if raw_paper_l < 60.0:
        score -= min(25.0, (60.0 - raw_paper_l) * 2.0)

    return max(0, min(100, int(round(score))))


def calculate_match_score(
    d_e: float,
    undertone_ref: str,
    undertone_cand: str,
) -> Tuple[float, str, str]:
    """Calculate combined match score with undertone penalty and qualitative label.

    Returns:
        (total_penalty_score, match_label, human_readable_explanation)
    """
    # Undertone penalties: 0 = same, 1.5 = adjacent (neutral to warm/cool), 4.0 = opposite (warm to cool)
    if undertone_ref == undertone_cand:
        undertone_penalty = 0.0
    elif "neutral" in (undertone_ref, undertone_cand):
        undertone_penalty = 1.5
    else:
        undertone_penalty = 4.0

    total_score = d_e + undertone_penalty

    if d_e <= 2.0 and undertone_penalty == 0.0:
        label = "match"
        explanation = f"ΔE {d_e:.1f} — hard to tell apart; same {undertone_ref} undertone."
    elif d_e <= 2.0:
        label = "close"
        explanation = f"ΔE {d_e:.1f} — hard to tell apart in depth, but differs in undertone ({undertone_cand} vs {undertone_ref})."
    elif d_e <= 4.0:
        label = "close"
        explanation = f"ΔE {d_e:.1f} — close, wearable shade match with minor tone variance."
    else:
        label = "different"
        explanation = f"ΔE {d_e:.1f} — visibly different shade."

    return total_score, label, explanation
