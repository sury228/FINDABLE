"""Unit tests for Prompt 4: PayPal sandbox flow, webhooks, error handling, idempotency, and validations."""

import json
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.config import get_settings
from app.db import get_session, seed_db
from app.models import Order, Product, Shade, Shop, PayPalLog
from app.paypal.client import paypal_client
from app.paypal.webhooks import verify_webhook_signature, process_webhook_event


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


# ── 1. Webhook Signature Verification Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_verify_webhook_signature_fails_when_live_and_no_webhook_id(monkeypatch):
    """verify_webhook_signature must return False when PAYPAL_WEBHOOK_ID is empty in live mode."""
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_PAYPAL", False)
    
    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-transmission-id": "trans-123",
        "paypal-transmission-sig": "sig-123",
        "paypal-transmission-time": "2026-11-11T12:00:00Z",
    }
    # Empty webhook_id in live mode
    is_valid = await verify_webhook_signature(headers, b'{"event_type":"PAYMENT.CAPTURE.COMPLETED"}', "")
    assert is_valid is False


@pytest.mark.asyncio
async def test_webhook_endpoint_rejects_unverified_signature(client, monkeypatch):
    """POST /webhooks/paypal returns 400 when signature fails verification."""
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_PAYPAL", False)
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "")  # Will cause failure in live mode

    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-transmission-id": "trans-123",
        "paypal-transmission-sig": "sig-123",
        "paypal-transmission-time": "2026-11-11T12:00:00Z",
    }
    res = client.post("/webhooks/paypal", content=b'{"id":"WH-123","event_type":"PAYMENT.CAPTURE.COMPLETED"}', headers=headers)
    assert res.status_code == 400
    assert "Invalid PayPal webhook signature" in res.json()["detail"]


# ── 2. Webhook Resource Order Lookup by Invoice ID ────────────────────────────

@pytest.mark.asyncio
async def test_webhook_order_lookup_by_invoice_id(session: Session):
    """Webhook order lookup finds order by resource.invoice_id and updates status."""
    order = Order(
        id="ord_test_inv",
        invoice_id="FDB-TEST-INV-1",
        status="CREATED",
        items_json="[]",
        total=28.0,
        currency="USD",
    )
    session.add(order)
    session.commit()

    event = {
        "id": "WH-EVT-001",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-TEST-999",
            "invoice_id": "FDB-TEST-INV-1",
            "custom_id": "fdb:truncated_hash",
        }
    }
    processed = await process_webhook_event(session, event)
    assert processed is True

    updated_order = session.get(Order, "ord_test_inv")
    assert updated_order.status == "COMPLETED"
    assert updated_order.capture_id == "CAP-TEST-999"


# ── 3. create_checkout Validations (Empty cart, unknown shade, stock, Decimal) ──

@pytest.mark.asyncio
async def test_create_checkout_validations(session: Session):
    """create_checkout rejects empty carts, unknown shade IDs, and checks stock."""
    from app.services import create_checkout

    # Empty cart
    with pytest.raises(ValueError, match="Cart is empty"):
        await create_checkout(session, [])

    # Unknown shade
    with pytest.raises(ValueError, match="Unknown shade_id"):
        await create_checkout(session, [{"shade_id": "shd_nonexistent", "quantity": 1}])

    # Out of stock
    product = session.exec(select(Product)).first()
    shade = session.exec(select(Shade).where(Shade.product_id == product.id)).first()
    product.stock = 2
    session.add(product)
    session.commit()

    with pytest.raises(ValueError, match="Insufficient stock"):
        await create_checkout(session, [{"shade_id": shade.id, "quantity": 5}])

    # Success creates order with invoice_id and Decimal accuracy
    # Force mock mode for create_checkout in this unit test to avoid external network calls
    orig_mock = paypal_client.is_mock
    paypal_client.is_mock = True
    try:
        checkout = await create_checkout(session, [{"shade_id": shade.id, "quantity": 1}])
        assert "order_id" in checkout
        assert "invoice_id" in checkout
        assert checkout["invoice_id"].startswith("FDB-")
        saved_order = session.get(Order, checkout["order_id"])
        assert saved_order.invoice_id == checkout["invoice_id"]
        assert saved_order.total == product.price_usd
    finally:
        paypal_client.is_mock = orig_mock


# ── 4. /checkout/return Flow & Idempotency ────────────────────────────────────

def test_checkout_return_404_when_order_not_found(client):
    """/checkout/return returns 404 when token/internal_id is missing or unknown."""
    res = client.get("/checkout/return?internal_id=ord_ghost_order")
    assert res.status_code == 404


def test_checkout_return_idempotency_and_capture(client, session: Session):
    """Capture marks order COMPLETED, and if already COMPLETED, simply redirects."""
    order = Order(
        id="ord_capture_test",
        paypal_order_id="MOCK-ORD-CAPTURE",
        invoice_id="FDB-ORD_CAPTURE_TEST",
        status="CREATED",
        items_json="[]",
        total=28.0,
        currency="USD",
    )
    session.add(order)
    session.commit()

    # Ensure mock mode
    paypal_client.is_mock = True

    # First return call captures order
    res = client.get(f"/checkout/return?internal_id={order.id}", follow_redirects=False)
    assert res.status_code == 307
    assert "/dashboard?captured=true" in res.headers["location"]

    session.refresh(order)
    assert order.status == "COMPLETED"
    assert order.capture_id is not None

    # Second return call is idempotent redirect without re-capturing
    res2 = client.get(f"/checkout/return?internal_id={order.id}", follow_redirects=False)
    assert res2.status_code == 307
    assert "/dashboard?captured=true" in res2.headers["location"]


# ── 5. PayPal Call Logs Persistence ──────────────────────────────────────────

def test_paypal_call_logs_persisted_in_table(session: Session, monkeypatch):
    """PayPal API calls record to PayPalLog table and can be queried."""
    import app.db
    monkeypatch.setattr(app.db, "engine", session.get_bind())
    
    paypal_client._log_call("POST", "/v2/checkout/orders", 201, {"id": "TEST-123", "debug_id": "dbg_456"})
    
    logs = session.exec(select(PayPalLog).where(PayPalLog.debug_id == "dbg_456")).all()
    assert len(logs) >= 1
    assert logs[0].method == "POST"
    assert logs[0].endpoint == "/v2/checkout/orders"
    assert logs[0].status == 201
