"""Unit tests for PayPal REST client and offline mock execution."""

import pytest
from app.paypal.client import PayPalClient
from app.paypal.webhooks import verify_webhook_signature


@pytest.mark.asyncio
async def test_paypal_mock_order_lifecycle():
    """Verify PayPal client mock mode creates and captures orders without real API calls."""
    # Force mock mode regardless of env settings
    client = PayPalClient()
    # Override is_mock to True so the test always exercises mock code paths
    client.is_mock = True

    # 1. Create Order
    order_res = await client.create_order(
        amount=28.00,
        currency="USD",
        items=[{"name": "Honey 04", "shade_id": "shd_honey04", "price": 28.00, "quantity": 1}],
        custom_id="fdb:7f83b1657ff1fc53",
        invoice_id="FDB-TEST-001",
        return_url="http://localhost:8000/checkout/return",
        cancel_url="http://localhost:8000/checkout/cancel",
    )

    assert "id" in order_res
    assert order_res["id"].startswith("MOCK-ORD-")
    assert order_res["status"] == "CREATED"
    assert any(link.get("rel") == "payer-action" for link in order_res.get("links", []))

    # 2. Capture Order
    capture_res = await client.capture_order(order_res["id"])
    assert capture_res["status"] == "COMPLETED"

    # 3. Refund Order
    refund_res = await client.refund_capture("MOCK-CAP-12345", amount=28.00)
    assert refund_res["status"] == "COMPLETED"
    assert refund_res["id"].startswith("MOCK-REF-")


@pytest.mark.asyncio
async def test_paypal_mock_webhook_verification(monkeypatch):
    """Verify webhook signature verification gracefully accepts mock payloads in offline mode."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "MOCK_PAYPAL", True)

    headers = {"paypal-auth-algo": "SHA256withRSA"}
    is_valid = await verify_webhook_signature(headers, b'{"event_type":"PAYMENT.CAPTURE.COMPLETED"}', "")
    assert is_valid is True

