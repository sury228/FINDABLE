"""Unit tests for Prompt 6: MCP server tools, mounting, error handling, and discovery."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.db import seed_db
from app.mcp_server import (
    search_products,
    match_shade,
    get_shade_passport,
    create_checkout,
    get_order_status,
)


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


def test_mcp_info_endpoint():
    """Verify /mcp-info returns all 5 renamed tools and streamable HTTP transport info."""
    client = TestClient(app)
    res = client.get("/mcp-info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    tool_names = [t["name"] for t in data["tools"]]
    assert "search_products" in tool_names
    assert "match_shade" in tool_names
    assert "get_shade_passport" in tool_names
    assert "create_checkout" in tool_names
    assert "get_order_status" in tool_names
    assert "open_shade_promise" not in tool_names


def test_mcp_streamable_http_mount():
    """Verify the MCP streamable HTTP application is mounted at /mcp without errors."""
    with TestClient(app) as client:
        # The streamable HTTP app is mounted at /mcp; checking GET /mcp/ returns non-404
        res = client.get("/mcp/")
        assert res.status_code != 404


def test_mcp_tools_execution_and_clean_errors():
    """Verify all 5 tools return valid results or human-readable error strings."""
    # 1. search_products
    prods = search_products(category="foundation")
    assert isinstance(prods, list)

    # 2. match_shade with valid ref
    matches = match_shade(reference="REF-SAMPLE")
    assert isinstance(matches, list)

    # 2b. match_shade with bad ref returns clean string error (not unhandled exception)
    bad_match = match_shade(reference="REF-UNKNOWN")
    assert isinstance(bad_match, str)
    assert "Error" in bad_match

    # 3. get_shade_passport with unknown shade returns readable error
    bad_passport = get_shade_passport(shade_id="shd_does_not_exist")
    assert isinstance(bad_passport, str)
    assert "not found" in bad_passport.lower() or "error" in bad_passport.lower()
