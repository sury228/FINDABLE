"""Tests for Prompt 3: shopper side, honest matching, /api/references, /api/measure, match_shade."""

import io
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import get_session, seed_db
from app.models import BuyerReference, Shade, Product, Shop


# ── In-memory test database ───────────────────────────────────────────────────

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_db(session)
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ── /api/references ───────────────────────────────────────────────────────────

def test_create_reference(client):
    """Creating a reference stores it in the DB and returns a valid REF code."""
    res = client.post("/api/references", json={"lab": [62.4, 13.9, 24.1]})
    assert res.status_code == 200
    data = res.json()
    assert data["ref_code"].startswith("REF-")
    assert data["hex"].startswith("#")
    assert len(data["lab"]) == 3


def test_create_reference_missing_lab(client):
    """Missing lab should return 400."""
    res = client.post("/api/references", json={"hex": "#C08C6C"})
    assert res.status_code == 400


# ── match_shade honest errors ─────────────────────────────────────────────────

def test_match_shade_unknown_ref_raises(client, session):
    """Unknown REF code should return error message, not silently use a default."""
    from app.services import match_shade
    with pytest.raises(ValueError, match="Unknown reference code"):
        match_shade(session, "REF-DOESNOTEXIST")


def test_match_shade_bad_hex_raises(session):
    """Invalid hex should raise ValueError."""
    from app.services import match_shade
    with pytest.raises(ValueError, match="Invalid hex"):
        match_shade(session, "#ZZZZZZ")


def test_match_shade_no_default_on_bare_keyword(session):
    """Bare keyword without REF/hex/lab should raise ValueError (no silent default)."""
    from app.services import match_shade
    with pytest.raises(ValueError):
        match_shade(session, "honey")


def test_match_shade_known_ref(client, session):
    """Sample REF from seed returns top-5 matches, sorted by ΔE."""
    # REF-SAMPLE is seeded
    from app.services import match_shade
    matches = match_shade(session, "REF-SAMPLE", limit=5)
    assert len(matches) >= 1
    # Sorted ascending by match_score
    scores = [m["match_score"] for m in matches]
    assert scores == sorted(scores)
    # Top match should have small ΔE (Honey 04 is designed to match REF-SAMPLE)
    assert matches[0]["delta_e"] <= 5.0


def test_match_shade_hex(session):
    """Hex reference resolves correctly through hex_to_lab."""
    from app.services import match_shade
    matches = match_shade(session, "#C08C6C", limit=5)
    assert len(matches) >= 1


def test_match_shade_lab(session):
    """Direct [L, a, b] list resolves correctly."""
    from app.services import match_shade
    matches = match_shade(session, [62.4, 13.9, 24.1], limit=5)
    assert len(matches) >= 1


# ── ΔE label wording ─────────────────────────────────────────────────────────

def test_labels_no_exact_match_wording():
    """Labels must not use 'exact match' or 'virtually imperceptible'."""
    from app.color.metrics import calculate_match_score
    for d_e in [0.5, 1.5, 2.5, 5.0]:
        _, label, explanation = calculate_match_score(d_e, "warm", "warm")
        assert "exact match" not in explanation.lower()
        assert "virtually imperceptible" not in explanation.lower()

    # Correct wording for ΔE ≤ 2
    _, _, expl = calculate_match_score(1.0, "warm", "warm")
    assert "hard to tell apart" in expl.lower()


# ── /api/measure endpoint ─────────────────────────────────────────────────────

def _make_test_image(w=200, h=150, color=(192, 140, 108)):
    """Create a solid-color PNG in memory."""
    arr = np.full((h, w, 3), color, dtype=np.uint8)
    from PIL import Image
    img = Image.fromarray(arr, 'RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_api_measure_missing_paper(client):
    """Missing paper box should return 400."""
    buf = _make_test_image()
    boxes = json.dumps({"swatches": [[0.3, 0.3, 0.7, 0.7]]})
    res = client.post(
        "/api/measure",
        data={"boxes": boxes},
        files={"file": ("test.png", buf, "image/png")},
    )
    assert res.status_code == 400
    assert "paper" in res.json()["detail"].lower()


def test_api_measure_missing_swatch(client):
    """Missing swatches should return 400."""
    buf = _make_test_image()
    boxes = json.dumps({"paper": [0.0, 0.0, 0.3, 0.3], "swatches": []})
    res = client.post(
        "/api/measure",
        data={"boxes": boxes},
        files={"file": ("test.png", buf, "image/png")},
    )
    assert res.status_code == 400


def test_api_measure_valid(client):
    """Valid measure request returns corrected lab, hex, confidence for each swatch."""
    buf = _make_test_image(300, 300)
    boxes = json.dumps({
        "paper": [0.0, 0.0, 0.3, 0.3],
        "swatches": [[0.4, 0.4, 0.8, 0.8]],
    })
    res = client.post(
        "/api/measure",
        data={"boxes": boxes},
        files={"file": ("test.png", buf, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "swatches" in data
    assert len(data["swatches"]) == 1
    sw = data["swatches"][0]
    assert "corrected" in sw
    assert "raw_hex" in sw
    assert "confidence" in sw
    corrected = sw["corrected"]
    assert "lab" in corrected and len(corrected["lab"]) == 3
    assert "hex" in corrected
    assert "depth" in corrected
    assert "undertone" in corrected


def test_api_measure_whitepaper_correction():
    """White-balance correction reduces the colour error caused by a yellow light cast."""
    from app.color.pipeline import white_balance, swatch_lab, srgb_to_linear, delta_e, rgb_to_lab
    import numpy as np

    # Build a 100×100 synthetic image in two zones:
    #   top-left 30×30  = white paper (should be near-white after balance)
    #   bottom-right 60×60 = swatch (honey-tan colour)
    true_swatch_rgb = np.array([192, 140, 108], dtype=np.uint8)
    true_paper_rgb  = np.array([230, 230, 230], dtype=np.uint8)  # neutral grey-white

    h, w = 100, 100
    img_true = np.zeros((h, w, 3), dtype=np.uint8)
    img_true[0:30, 0:30] = true_paper_rgb
    img_true[35:95, 35:95] = true_swatch_rgb

    # Apply a yellow-green cast to the whole image
    cast = np.array([1.25, 1.15, 0.65])
    img_cast = np.clip(img_true.astype(np.float32) * cast, 0, 255).astype(np.uint8)

    paper_box  = [0, 0, 30, 30]
    swatch_box = [35, 35, 95, 95]
    true_lab   = rgb_to_lab(true_swatch_rgb.tolist())

    # Raw (no white balance)
    raw_lin = srgb_to_linear(img_cast.astype(np.float64))
    raw_lab = swatch_lab(raw_lin, swatch_box)
    raw_de  = delta_e(raw_lab.tolist(), true_lab)

    # Corrected
    balanced      = white_balance(img_cast, paper_box, target=0.85)
    corrected_lab = swatch_lab(balanced, swatch_box)
    corrected_de  = delta_e(corrected_lab.tolist(), true_lab)

    # After correction the error must be strictly smaller than without correction
    assert corrected_de < raw_de, (
        f"White-balance should reduce ΔE: corrected={corrected_de:.2f}, raw={raw_de:.2f}"
    )
