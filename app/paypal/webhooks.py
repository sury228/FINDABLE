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
    if settings.MOCK_PAYPAL or not webhook_id:
        # In offline/mock mode or local test runs, bypass network signature check
        return True

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
        # Find order by custom_id or capture reference
        custom_id = resource.get("custom_id")
        order = None
        if custom_id:
            order = session.exec(select(Order).where(Order.passport_bundle_hash == custom_id.replace("fdb:", ""))).first()

        if order:
            order.status = "COMPLETED"
            order.capture_id = capture_id
            session.add(order)

    elif event_type == "PAYMENT.CAPTURE.REFUNDED":
        capture_id = resource.get("capture_id")
        if capture_id:
            order = session.exec(select(Order).where(Order.capture_id == capture_id)).first()
            if order:
                order.status = "REFUNDED"
                session.add(order)

    session.commit()
    return True

