"""PayPal webhook signature verification and idempotent event processing."""

import logging
from typing import Any, Dict
import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models import Order, WebhookEvent
from app.paypal.client import paypal_client

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_webhook_signature(
    headers: Dict[str, str],
    body_bytes: bytes,
    webhook_id: str,
) -> bool:
    """Verify PayPal webhook authenticity using PayPal's verification endpoint."""
    if settings.MOCK_PAYPAL:
        # In offline/mock mode bypass network signature check
        return True

    # In live mode, verify_webhook_signature must return False when PAYPAL_WEBHOOK_ID is empty
    if not webhook_id or not webhook_id.strip():
        logger.warning("PayPal webhook verification failed: PAYPAL_WEBHOOK_ID is empty in live mode.")
        return False

    token = await paypal_client.get_access_token()
    verify_url = f"{settings.PAYPAL_BASE_URL.rstrip('/')}/v1/notifications/verify-webhook-signature"

    payload = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": webhook_id,
        "webhook_event": httpx.Response(200, content=body_bytes).json(),
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            verify_url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        if res.status_code == 200:
            return res.json().get("verification_status") == "SUCCESS"
        return False


async def process_webhook_event(session: Session, event: Dict[str, Any]) -> bool:
    """Process PayPal webhook event with strict idempotency."""
    event_id = event.get("id")
    event_type = event.get("event_type")

    if not event_id:
        return False

    # Idempotency check: Skip if already recorded
    existing = session.get(WebhookEvent, event_id)
    if existing:
        logger.info("Webhook event %s already processed. Skipping.", event_id)
        return True

    # Record event
    record = WebhookEvent(paypal_event_id=event_id, event_type=event_type or "UNKNOWN")
    session.add(record)

    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        capture_id = resource.get("id")
        # Store invoice_id on Order model and look up by resource.invoice_id (fallback to capture id / custom_id)
        invoice_id = resource.get("invoice_id")
        order = None
        if invoice_id:
            order = session.exec(select(Order).where(Order.invoice_id == invoice_id)).first()
        if not order and capture_id:
            order = session.exec(select(Order).where(Order.capture_id == capture_id)).first()
        if not order:
            custom_id = resource.get("custom_id")
            if custom_id:
                clean_custom = custom_id.replace("fdb:", "")
                order = session.exec(select(Order).where(Order.passport_bundle_hash.startswith(clean_custom))).first()

        if order:
            order.status = "COMPLETED"
            order.capture_id = capture_id
            session.add(order)

    elif event_type == "PAYMENT.CAPTURE.REFUNDED":
        # Look up by invoice_id or fall back to capture_id
        invoice_id = resource.get("invoice_id")
        capture_id = resource.get("capture_id") or resource.get("id")
        order = None
        if invoice_id:
            order = session.exec(select(Order).where(Order.invoice_id == invoice_id)).first()
        if not order and capture_id:
            order = session.exec(select(Order).where(Order.capture_id == capture_id)).first()

        if order:
            order.status = "REFUNDED"
            session.add(order)

    session.commit()
    return True

