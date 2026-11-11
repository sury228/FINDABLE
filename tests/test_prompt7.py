"""Unit tests for Prompt 7: Complete removal of Shade Promise, stray files, and truthful docs."""

import os
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_shade_promise_route_removed():
    """Verify /promise/{order_id} returns 404 now that Shade Promise is removed."""
    client = TestClient(app)
    res = client.get("/promise/ord_test123")
    assert res.status_code == 404


def test_promise_claim_model_removed():
    """Verify PromiseClaim is not in app.models."""
    import app.models
    assert not hasattr(app.models, "PromiseClaim")


def test_open_shade_promise_service_removed():
    """Verify open_shade_promise is not in app.services."""
    import app.services
    assert not hasattr(app.services, "open_shade_promise")


def test_stray_files_deleted():
    """Verify junk root files and simulated benchmark scripts are deleted."""
    stray_files = [
        "index.html",
        "MY_QUERY.md",
        "running_detail.txt",
        "run findable",
        "run findable.md",
        "push_to_github.bat",
        "run_findable.bat",
        "run_findable.ps1",
        "RUN_FINDABLE.md",
        "bench/run.py",
        "bench/results.csv",
        "bench/queries.json",
    ]
    for f in stray_files:
        assert not os.path.exists(f), f"Stray file {f} should be deleted"

    # bench/README.md should exist
    assert os.path.exists("bench/README.md")


def test_requirements_cleaned():
    """Verify requirements.txt does not contain unused heavyweight dependencies."""
    with open("requirements.txt", "r", encoding="utf-8") as f:
        reqs = f.read().lower()
    assert "opencv" not in reqs
    assert "anthropic" not in reqs
    assert "google-genai" not in reqs
    assert "pillow" in reqs
    assert "scikit-image" in reqs


def test_render_yaml_free_plan():
    """Verify render.yaml specifies plan: free."""
    with open("render.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    assert "plan: free" in content


def test_judges_page_4_step_evaluation_flow():
    """Verify judges page presents a 4-step evaluation flow."""
    client = TestClient(app)
    res = client.get("/judges")
    assert res.status_code == 200
    html = res.text
    assert "Seller Studio" in html
    assert "Shopper" in html or "Match" in html
    assert "PayPal" in html
    assert "Dashboard" in html or "Audit" in html
    assert "Shade Promise" not in html

