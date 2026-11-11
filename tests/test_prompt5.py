"""Unit tests for Prompt 5: AI Shopper Agent with Groq tool-calling, listing generation, and rule fallback."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.config import get_settings
from app.db import seed_db
from app.llm.agent import run_agent_turn, SYSTEM_PROMPT
from app.models import Product, Shade, BuyerReference


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


# ── 1. Fallback to Rules Mode When No API Key ─────────────────────────────────

@pytest.mark.asyncio
async def test_agent_fallback_to_rules_when_no_api_key(session: Session, monkeypatch):
    """When LLM_API_KEY is unset, agent executes rules mode and flags mode='rules'."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    # Matching query with known reference
    turn = await run_agent_turn(
        session=session,
        user_message="My shade is REF-SAMPLE, find me a match under $30",
    )
    assert turn["mode"] == "rules"
    assert "reply" in turn
    assert len(turn["tools_called"]) >= 1
    assert turn["tools_called"][0]["tool"] == "match_shade"
    assert len(turn["cards"]) >= 1


@pytest.mark.asyncio
async def test_agent_rules_asks_for_swatch_if_no_reference(session: Session, monkeypatch):
    """When no reference provided in rules mode, agent asks for swatch upload."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    turn = await run_agent_turn(
        session=session,
        user_message="Find my foundation match please",
    )
    assert turn["mode"] == "rules"
    assert "upload a swatch photo" in turn["reply"].lower()


@pytest.mark.asyncio
async def test_agent_rules_asks_for_shade_if_ordering_without_id(session: Session, monkeypatch):
    """When order intent has no shade id, agent prompts for shade."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    turn = await run_agent_turn(
        session=session,
        user_message="I want to buy foundation right now",
    )
    assert turn["mode"] == "rules"
    assert "which shade would you like to order" in turn["reply"].lower()


# ── 2. Real Groq Tool Calling Simulation ──────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_groq_tool_calling_loop(session: Session, monkeypatch):
    """With Groq key, agent chooses match_shade tool, loops, and returns mode='llm'."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "gsk_test_key_123456789")
    monkeypatch.setattr(settings, "LLM_MODEL", "llama-3.3-70b-versatile")

    # Mock Groq client response round 1: tool call to match_shade
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_abc123"
    tool_call_obj.function.name = "match_shade"
    tool_call_obj.function.arguments = json.dumps({"reference": "REF-SAMPLE", "max_price": 30.0})

    msg_round_1 = MagicMock()
    msg_round_1.content = None
    msg_round_1.tool_calls = [tool_call_obj]

    choice_round_1 = MagicMock()
    choice_round_1.message = msg_round_1

    resp_round_1 = MagicMock()
    resp_round_1.choices = [choice_round_1]

    # Mock Groq client response round 2: text completion after tool output
    msg_round_2 = MagicMock()
    msg_round_2.content = "I found your match! Honey 04 has a ΔE of 1.2 which is hard to tell apart."
    msg_round_2.tool_calls = None

    choice_round_2 = MagicMock()
    choice_round_2.message = msg_round_2

    resp_round_2 = MagicMock()
    resp_round_2.choices = [choice_round_2]

    # Async mock for client.chat.completions.create
    mock_create = AsyncMock(side_effect=[resp_round_1, resp_round_2])

    with patch("groq.AsyncGroq") as mock_groq_class:
        mock_instance = MagicMock()
        mock_instance.chat.completions.create = mock_create
        mock_groq_class.return_value = mock_instance

        turn = await run_agent_turn(
            session=session,
            user_message="find my shade under $30 with REF-SAMPLE",
        )

        assert turn["mode"] == "llm"
        assert "Honey 04" in turn["reply"]
        assert len(turn["tools_called"]) == 1
        assert turn["tools_called"][0]["tool"] == "match_shade"
        assert turn["tools_called"][0]["args"]["reference"] == "REF-SAMPLE"
        assert len(turn["cards"]) == 1
        assert turn["cards"][0]["type"] == "matches"


# ── 3. Product Listing Generation ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listing_generation_empty_when_no_key(monkeypatch):
    """When LLM_API_KEY is empty, listing draft returns empty string."""
    from fastapi.testclient import TestClient
    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    client = TestClient(app)
    res = client.post("/api/listing/draft", json={"product_name": "Silk Foundation"})
    assert res.status_code == 200
    assert res.json()["description"] == ""
