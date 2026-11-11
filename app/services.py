"""Core domain services shared by MCP server, Web Agent, and UI routes."""

import json
import math
import uuid
from typing import Any, Dict, List, Optional, Union
from sqlmodel import Session, select

from app.color.metrics import calculate_ita, calculate_match_score, depth_from_ita, undertone_from_hue
from app.color.pipeline import delta_e, hex_to_lab, lab_to_hex
from app.config import get_settings
from app.models import BuyerReference, Order, Product, Shade
from app.passport import compute_bundle_hash, create_shade_passport_dict, sign_passport
from app.paypal.client import paypal_client

settings = get_settings()


def search_products(
    session: Session,
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    undertone: Optional[str] = None,
    depth: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Search products with keyword matching, price filtering, and shade metadata."""
    stmt = select(Product)
    if category:
        stmt = stmt.where(Product.category == category)
    if max_price is not None:
        stmt = stmt.where(Product.price_usd <= max_price)

    products = session.exec(stmt).all()
    results = []

    for p in products:
        if query and query.strip():
            q = query.lower()
            if q not in p.name.lower() and q not in p.description.lower():
                continue

        # Get attached shades
        shades = session.exec(select(Shade).where(Shade.product_id == p.id)).all()
        if undertone:
            shades = [s for s in shades if s.undertone == undertone]
        if depth:
            shades = [s for s in shades if s.depth == depth]

        results.append({
            "product_id": p.id,
            "name": p.name,
            "category": p.category,
            "price_usd": p.price_usd,
            "finish": p.finish,
            "coverage": p.coverage,
            "shade_count": len(shades),
            "available_undertones": list(set(s.undertone for s in shades)),
            "available_depths": list(set(s.depth for s in shades)),
        })
        if len(results) >= limit:
            break

    return results


def match_shade(
    session: Session,
    reference: Union[str, List[float]],
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Find closest matching shades based on CIEDE2000 ΔE and undertone alignment.

    Raises ValueError if the reference cannot be resolved. No silent defaults.
    """
    ref_lab: Optional[List[float]] = None
    ref_undertone: Optional[str] = None

    # 1. Resolve reference to CIELAB coordinates
    if isinstance(reference, str) and reference.upper().startswith("REF-"):
        clean_code = reference.upper().strip()
        buyer_ref = session.exec(
            select(BuyerReference).where(BuyerReference.ref_code == clean_code)
        ).first()
        if not buyer_ref:
            raise ValueError(f"Unknown reference code: {clean_code}. Please upload a swatch photo first to get a valid REF code.")
        ref_lab = [buyer_ref.L, buyer_ref.a, buyer_ref.b]
    elif isinstance(reference, list) and len(reference) == 3:
        ref_lab = [float(v) for v in reference]
    elif isinstance(reference, str) and reference.startswith("#"):
        try:
            ref_lab = hex_to_lab(reference)
        except ValueError:
            raise ValueError(f"Invalid hex color: {reference}. Expected format: #RRGGBB")
    else:
        raise ValueError(
            f"Cannot resolve reference '{reference}'. "
            "Provide a REF-XXXX code, a hex color (#RRGGBB), or a [L, a, b] array."
        )

    if ref_lab is None:
        raise ValueError("Could not determine reference color. Please upload a swatch photo first.")

    # Compute reference undertone from its hue angle
    a_val, b_val = ref_lab[1], ref_lab[2]
    ref_hue_deg = math.degrees(math.atan2(b_val, a_val)) % 360.0
    ref_undertone = undertone_from_hue(ref_hue_deg)

    # 2. Query candidates
    stmt = select(Shade, Product).join(Product, Shade.product_id == Product.id)
    if category:
        stmt = stmt.where(Product.category == category)
    if max_price is not None:
        stmt = stmt.where(Product.price_usd <= max_price)

    rows = session.exec(stmt).all()
    candidates = []

    for shade, product in rows:
        cand_lab = [shade.L, shade.a, shade.b]
        d_e = delta_e(ref_lab, cand_lab)
        score, label, explanation = calculate_match_score(
            d_e=d_e,
            undertone_ref=ref_undertone,
            undertone_cand=shade.undertone,
        )
        candidates.append({
            "shade_id": shade.id,
            "product_id": product.id,
            "product_name": product.name,
            "shade_name": shade.shade_name,
            "hex": shade.hex,
            "price": product.price_usd,
            "delta_e": round(d_e, 2),
            "match_score": round(score, 2),
            "undertone_match": (shade.undertone == ref_undertone),
            "label": label,
            "explanation": explanation,
            "passport_hash": shade.passport_hash,
        })

    # Sort candidates by combined score
    candidates.sort(key=lambda x: x["match_score"])
    return candidates[:limit]


def get_shade_passport_service(session: Session, shade_id: str) -> Optional[Dict[str, Any]]:
    """Generate and return canonical signed Shade Passport document for a shade."""
    shade = session.get(Shade, shade_id)
    if not shade:
        return None
    product = session.get(Product, shade.product_id)

    # Use stored measured_at for passport consistency
    measured_at_str = shade.measured_at.isoformat() if shade.measured_at else None

    # Determine method reference based on source
    method_reference = "white paper" if getattr(shade, "source", "seed") == "measured" else "seed data (not photographed)"

    passport = create_shade_passport_dict(
        shade_id=shade.id,
        product_id=product.id if product else "prd_unknown",
        product_name=product.name if product else "Unknown Product",
        category=product.category if product else "foundation",
        price_usd=product.price_usd if product else 28.00,
        shade_name=shade.shade_name,
        hex_color=shade.hex,
        lab=[shade.L, shade.a, shade.b],
        chroma=shade.chroma,
        hue_deg=shade.hue_deg,
        ita_deg=shade.ita_deg,
        depth=shade.depth,
        undertone=shade.undertone,
        confidence=shade.confidence,
        measured_at=measured_at_str,
        method_reference=method_reference,
    )
    p_hash, p_sig = sign_passport(passport)
    passport["hash"] = p_hash
    passport["signature"] = p_sig
    return passport


async def create_checkout(
    session: Session,
    items: List[Dict[str, Any]],
    agent_name: str = "web-agent",
) -> Dict[str, Any]:
    """Create a verified PayPal order strictly using database-authoritative pricing."""
    from decimal import Decimal

    if not items:
        raise ValueError("Cart is empty. Please add at least one shade to your order.")

    total_amount = Decimal("0.00")
    verified_items = []
    passport_hashes = []

    for item in items:
        shade_id = item.get("shade_id")
        if not shade_id:
            raise ValueError("Each item must include a shade_id.")
        qty = int(item.get("quantity", 1))
        if qty <= 0:
            raise ValueError("Quantity must be greater than zero.")

        shade = session.get(Shade, shade_id)
        if not shade:
            raise ValueError(f"Unknown shade_id: {shade_id}. Please check the catalog.")

        product = session.get(Product, shade.product_id)
        if not product:
            raise ValueError(f"Product not found for shade {shade_id}.")

        # Check stock
        if product.stock < qty:
            raise ValueError(f"Insufficient stock for {product.name} ({shade.shade_name}). Available: {product.stock}, requested: {qty}.")

        price = Decimal(str(product.price_usd))
        line_total = price * Decimal(qty)
        total_amount += line_total

        verified_items.append({
            "shade_id": shade.id,
            "name": f"{product.name} - {shade.shade_name}",
            "price": float(price),
            "quantity": qty,
        })
        if shade.passport_hash:
            passport_hashes.append(shade.passport_hash)

    # Compute passport bundle hash for custom_id
    bundle_hash = compute_bundle_hash(passport_hashes) if passport_hashes else uuid.uuid4().hex
    custom_id = f"fdb:{bundle_hash[:16]}"
    internal_order_id = f"ord_{uuid.uuid4().hex[:8]}"
    invoice_id = f"FDB-{internal_order_id.upper()}"

    app_base = settings.APP_BASE_URL.rstrip("/")
    return_url = f"{app_base}/checkout/return?internal_id={internal_order_id}"
    cancel_url = f"{app_base}/checkout/cancel?internal_id={internal_order_id}"

    # Call PayPal client
    paypal_res = await paypal_client.create_order(
        amount=float(total_amount),
        currency="USD",
        items=verified_items,
        custom_id=custom_id,
        invoice_id=invoice_id,
        return_url=return_url,
        cancel_url=cancel_url,
    )

    paypal_order_id = paypal_res.get("id")
    approve_url = None
    for link in paypal_res.get("links", []):
        if link.get("rel") == "payer-action":
            approve_url = link.get("href")
            break

    # Persist Order in database
    order = Order(
        id=internal_order_id,
        paypal_order_id=paypal_order_id,
        invoice_id=invoice_id,
        status="CREATED",
        items_json=json.dumps(verified_items),
        total=float(total_amount),
        currency="USD",
        channel="agent" if "agent" in agent_name else "web",
        agent_name=agent_name,
        passport_bundle_hash=bundle_hash,
    )
    session.add(order)
    session.commit()

    return {
        "order_id": internal_order_id,
        "paypal_order_id": paypal_order_id,
        "invoice_id": invoice_id,
        "approve_url": approve_url,
        "total": float(total_amount),
        "currency": "USD",
        "custom_id": custom_id,
    }


async def get_order_status(session: Session, order_id: str) -> Dict[str, Any]:
    """Retrieve verified order status, enforcing that an agent cannot report PAID until COMPLETED."""
    order = session.get(Order, order_id)
    if not order:
        order = session.exec(select(Order).where(Order.paypal_order_id == order_id)).first()

    if not order:
        return {"error": "Order not found", "status": "UNKNOWN"}

    # Refresh from PayPal if needed
    if order.status == "CREATED" and order.paypal_order_id:
        try:
            pp_info = await paypal_client.get_order(order.paypal_order_id)
            if pp_info.get("status") == "COMPLETED":
                order.status = "COMPLETED"
                session.add(order)
                session.commit()
        except Exception:
            pass

    return {
        "order_id": order.id,
        "paypal_order_id": order.paypal_order_id,
        "status": order.status,
        "capture_id": order.capture_id,
        "total": order.total,
        "currency": order.currency,
        "items": json.loads(order.items_json) if order.items_json else [],
    }
