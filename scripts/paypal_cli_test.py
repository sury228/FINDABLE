"""Standalone test script to verify PayPal Sandbox order creation, capture, and refund.

Prints IDs and debug telemetry for Devpost and README proof.
Supports both MOCK_PAYPAL=1 (offline demo) and MOCK_PAYPAL=0 (live sandbox).
"""

import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.paypal.client import paypal_client


async def test_paypal_flow():
    print("\n=======================================================")
    print("   FINDABLE PAYPAL INTEGRATION VERIFICATION SCRIPT")
    print(f"   Mode: {'OFFLINE MOCK' if paypal_client.is_mock else 'LIVE SANDBOX'}")
    print("=======================================================\n")

    # 1. OAuth Access Token
    print("[1/4] Fetching OAuth2 Access Token...")
    try:
        token = await paypal_client.get_access_token()
        print(f"      [OK] Token acquired: {token[:16]}... (length: {len(token)})")
    except Exception as e:
        print(f"      [FAIL] OAuth error: {e}")
        return

    # 2. Create Order v2 with Shade Passport Bundle Hash
    print("\n[2/4] Creating PayPal Orders v2 transaction with custom_id...")
    sample_bundle_hash = "7f83b1657ff1fc53b92dc18148a1d65d"
    custom_id = f"fdb:{sample_bundle_hash[:16]}"
    invoice_id = "FDB-CLI-TEST-001"

    items = [
        {"name": "Serum Foundation — Honey 04", "shade_id": "shd_honey04", "price": 28.00, "quantity": 1}
    ]

    try:
        order_res = await paypal_client.create_order(
            amount=28.00,
            currency="USD",
            items=items,
            custom_id=custom_id,
            invoice_id=invoice_id,
            return_url="http://localhost:8000/checkout/return",
            cancel_url="http://localhost:8000/checkout/cancel",
        )
        order_id = order_res.get("id")
        approve_link = next((l["href"] for l in order_res.get("links", []) if l.get("rel") == "payer-action"), None)
        print(f"      [OK] PayPal Order ID: {order_id}")
        print(f"      [OK] Custom Passport ID: {custom_id}")
        print(f"      [OK] Status: {order_res.get('status')}")
        print(f"      [OK] Payer Approve Link: {approve_link}")
    except Exception as e:
        print(f"      [FAIL] Create Order error: {e}")
        return

    # 3. Capture Order
    print("\n[3/4] Capturing Order...")
    try:
        capture_res = await paypal_client.capture_order(order_id)
        capture_id = (
            capture_res.get("purchase_units", [{}])[0]
            .get("payments", {})
            .get("captures", [{}])[0]
            .get("id", "CAP-UNKNOWN")
        )
        print(f"      [OK] Capture Status: {capture_res.get('status')}")
        print(f"      [OK] Capture ID: {capture_id}")
    except Exception as e:
        print(f"      [FAIL] Capture error: {e}")
        return

    # 4. Payments v2 Refund (Shade Promise)
    print("\n[4/4] Executing Shade Promise Automated Refund...")
    try:
        refund_res = await paypal_client.refund_capture(
            capture_id=capture_id,
            amount=28.00,
            note_to_payer="Findable Shade Promise verification test refund.",
        )
        refund_id = refund_res.get("id")
        print(f"      [OK] Refund Status: {refund_res.get('status')}")
        print(f"      [OK] Refund ID: {refund_id}")
    except Exception as e:
        print(f"      [FAIL] Refund error: {e}")
        return

    print("\n=======================================================")
    print("   ALL PAYPAL CALLS COMPLETED SUCCESSFULLY!")
    print("   Copy these IDs for your Devpost testing notes:")
    print(f"   - Order ID:   {order_id}")
    print(f"   - Capture ID: {capture_id}")
    print(f"   - Refund ID:  {refund_id}")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(test_paypal_flow())

