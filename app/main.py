"""FastAPI application entry point, page routers, API endpoints, and MCP mounting."""

import io
import json
import math
import uuid
import numpy as np
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps
from sqlmodel import Session, select

from app.color.metrics import calculate_ita, compute_confidence, depth_from_ita, undertone_from_hue
from app.color.pipeline import (
    delta_e, hex_to_lab, lab_to_hex, rgb_to_lab,
    srgb_to_linear, linear_to_srgb, white_balance, swatch_lab, crop,
)
from app.config import get_settings
from app.db import get_session, init_db
from app.llm.agent import run_agent_turn
from app.models import BuyerReference, Order, Product, PromiseClaim, Shade, Shop
from app.passport import verify_passport, sign_passport, create_shade_passport_dict
from app.paypal.client import paypal_client
from app.paypal.webhooks import process_webhook_event, verify_webhook_signature
from app.services import (
    create_checkout,
    get_order_status,
    get_shade_passport_service,
    match_shade,
    open_shade_promise,
    search_products,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    init_db()
    yield


app = FastAPI(
    title="Findable",
    description="Physical Shade Data & Cryptographic Shade Passports for AI Shopping Agents via PayPal",
    version="1.0.0",
    lifespan=lifespan,
)

# Static and template configuration
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Mount FastMCP SSE transport if available
try:
    from app.mcp_server import mcp
    app.mount("/sse", mcp.sse_app())
except Exception:
    pass


# ==============================================================================
# Health Check & Root Redirect & MCP Discovery
# ==============================================================================

@app.get("/health")
def health_check():
    """Render health check endpoint."""
    return {"status": "healthy", "service": "findable", "mock_paypal": settings.MOCK_PAYPAL}


@app.get("/mcp")
def mcp_discovery():
    """MCP server discovery endpoint for AI Agents and judges."""
    return {
        "status": "online",
        "name": "Findable Shade Matcher",
        "protocol": "Model Context Protocol (FastMCP)",
        "version": "1.0.0",
        "transports": {
            "stdio": "python -m app.mcp_server",
            "sse": "/sse"
        },
        "tools_count": 5,
        "tools": [
            {
                "name": "search_products",
                "description": "Filter products by price, coverage, finish, and depth."
            },
            {
                "name": "match_shade",
                "description": "Calculate mathematical CIEDE2000 ΔE between customer reference and catalog shades."
            },
            {
                "name": "get_shade_passport",
                "description": "Retrieve SHA-256 canonical hash & HMAC-SHA256 verifiable signature."
            },
            {
                "name": "create_checkout",
                "description": "Initialize a verified server-authoritative PayPal Orders v2 checkout."
            },
            {
                "name": "get_order_status",
                "description": "Real-time PayPal order telemetry and status tracking."
            },
        ]
    }


@app.get("/")
def root_view():
    """Redirect root to judges page."""
    return RedirectResponse(url="/judges")


# ==============================================================================
# Web App View Routes (Jinja2)
# ==============================================================================

@app.get("/judges", response_class=HTMLResponse)
def judges_view(request: Request, session: Session = Depends(get_session)):
    """3-minute guided evaluation flow for hackathon judges."""
    shop = session.exec(select(Shop)).first()
    products = session.exec(select(Product)).all()
    shades = session.exec(select(Shade)).all()
    return templates.TemplateResponse(
        request=request,
        name="judges.html",
        context={
            "shop": shop,
            "products_count": len(products),
            "shades_count": len(shades),
            "is_mock": paypal_client.is_mock,
        },
    )


@app.get("/studio", response_class=HTMLResponse)
def studio_view(request: Request, session: Session = Depends(get_session)):
    """Seller Studio for swatch upload, canvas box annotation, and Shade Passport generation."""
    shop = session.exec(select(Shop)).first()
    products = session.exec(select(Product)).all()
    shades = session.exec(select(Shade)).all()
    return templates.TemplateResponse(
        request=request,
        name="studio.html",
        context={"shop": shop, "products": products, "shades": shades, "is_mock": paypal_client.is_mock},
    )


@app.get("/agent", response_class=HTMLResponse)
def agent_view(request: Request):
    """Shopper conversational web agent with inline swatch upload and PayPal checkout."""
    return templates.TemplateResponse(
        request=request,
        name="agent.html",
        context={"is_mock": paypal_client.is_mock},
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(request: Request, session: Session = Depends(get_session)):
    """Seller operations dashboard with AG Grid orders and PayPal call telemetry."""
    from app.models import PayPalLog
    orders = session.exec(select(Order).order_by(Order.created_at.desc())).all()
    claims = session.exec(select(PromiseClaim)).all()
    db_logs = session.exec(select(PayPalLog).order_by(PayPalLog.created_at.desc()).limit(15)).all()

    # If DB logs exist, format them for dashboard view; else fall back to in-memory call_logs
    if db_logs:
        paypal_logs = [
            {
                "method": log.method,
                "endpoint": log.endpoint,
                "status": log.status,
                "debug_id": log.debug_id or "-",
                "mode": log.mode,
            }
            for log in db_logs
        ]
    else:
        paypal_logs = paypal_client.call_logs[-15:]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "orders": orders,
            "claims": claims,
            "paypal_logs": paypal_logs,
            "is_mock": paypal_client.is_mock,
        },
    )


@app.get("/shop/{shop_id}", response_class=HTMLResponse)
def shop_view(shop_id: str, request: Request, session: Session = Depends(get_session)):
    """Direct consumer storefront with calibrated digital swatches and PayPal buttons."""
    shop = session.get(Shop, shop_id)
    if not shop:
        shop = session.exec(select(Shop)).first()
    products = session.exec(select(Product).where(Product.shop_id == shop.id)).all() if shop else []
    shades = session.exec(select(Shade)).all()
    return templates.TemplateResponse(
        request=request,
        name="shop.html",
        context={"shop": shop, "products": products, "shades": shades, "is_mock": paypal_client.is_mock},
    )


@app.get("/passport/{shade_id}", response_class=HTMLResponse)
def passport_view(shade_id: str, request: Request, session: Session = Depends(get_session)):
    """Human-readable Shade Passport inspection and cryptographic verification view."""
    passport = get_shade_passport_service(session, shade_id)
    if not passport:
        raise HTTPException(status_code=404, detail="Shade Passport not found.")
    is_valid = verify_passport(passport)
    return templates.TemplateResponse(
        request=request,
        name="passport.html",
        context={"passport": passport, "is_valid": is_valid, "is_mock": paypal_client.is_mock},
    )


@app.get("/promise/{order_id}", response_class=HTMLResponse)
def promise_view(order_id: str, request: Request, session: Session = Depends(get_session)):
    """Automated Shade Promise dispute resolution portal."""
    order = session.get(Order, order_id)
    return templates.TemplateResponse(
        request=request,
        name="promise.html",
        context={"order": order, "is_mock": paypal_client.is_mock},
    )


# ==============================================================================
# PayPal Checkout Flow (Return / Cancel Handlers)
# ==============================================================================

@app.get("/checkout/return")
async def checkout_return(
    token: Optional[str] = None,
    internal_id: Optional[str] = None,
    mock_approve: Optional[bool] = False,
    session: Session = Depends(get_session),
):
    """Handle shopper redirection after PayPal sandbox approval; captures the order."""
    order = None

    if internal_id:
        order = session.get(Order, internal_id)
    elif token:
        order = session.exec(select(Order).where(Order.paypal_order_id == token)).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found for return token/id.")

    # Idempotent capture: if already completed, just redirect
    if order.status == "COMPLETED":
        return RedirectResponse(url="/dashboard?captured=true")

    try:
        capture_res = await paypal_client.capture_order(order.paypal_order_id or "MOCK-ORD")
    except Exception as e:
        order.status = "FAILED"
        session.add(order)
        session.commit()
        return HTMLResponse(
            status_code=400,
            content=f"""
            <html><body style="background:#000;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ef4444;">PayPal Capture Failed</h1>
                <p>Error communicating with PayPal: {e}</p>
                <a href="/agent" style="color:#a3e635;">Return to Agent</a>
            </body></html>
            """
        )

    # Validate PayPal capture status and amount
    res_status = capture_res.get("status")
    purchase_unit = capture_res.get("purchase_units", [{}])[0]
    captures = purchase_unit.get("payments", {}).get("captures", [])
    capture_obj = captures[0] if captures else {}
    capture_status = capture_obj.get("status", res_status)
    capture_amount_val = capture_obj.get("amount", {}).get("value")
    capture_currency = capture_obj.get("amount", {}).get("currency_code")

    is_amount_matching = True
    if capture_amount_val:
        try:
            from decimal import Decimal
            is_amount_matching = (
                Decimal(str(capture_amount_val)) == Decimal(str(f"{order.total:.2f}"))
                and (not capture_currency or capture_currency == order.currency)
            )
        except Exception:
            is_amount_matching = False

    if (res_status == "COMPLETED" or capture_status == "COMPLETED") and is_amount_matching:
        order.status = "COMPLETED"
        real_cap_id = capture_obj.get("id")
        if real_cap_id:
            order.capture_id = real_cap_id
        elif paypal_client.is_mock:
            order.capture_id = f"MOCK-CAP-{uuid.uuid4().hex[:8].upper()}"
        else:
            order.status = "FAILED"
            session.add(order)
            session.commit()
            return HTMLResponse(
                status_code=400,
                content="""
                <html><body style="background:#000;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                    <h1 style="color:#ef4444;">Capture Failed</h1>
                    <p>No valid capture ID returned from PayPal.</p>
                    <a href="/agent" style="color:#a3e635;">Return to Agent</a>
                </body></html>
                """
            )
        session.add(order)
        session.commit()
        return RedirectResponse(url="/dashboard?captured=true")
    else:
        order.status = "FAILED"
        session.add(order)
        session.commit()
        return HTMLResponse(
            status_code=400,
            content=f"""
            <html><body style="background:#000;color:#fff;font-family:sans-serif;padding:40px;text-align:center;">
                <h1 style="color:#ef4444;">Payment Verification Failed</h1>
                <p>Status: {res_status or capture_status}. Amount matching: {is_amount_matching}.</p>
                <a href="/agent" style="color:#a3e635;">Return to Agent</a>
            </body></html>
            """
        )


@app.get("/checkout/cancel")
def checkout_cancel(internal_id: Optional[str] = None):
    """Handle shopper cancellation on PayPal checkout."""
    return RedirectResponse(url="/agent?cancelled=true")


@app.post("/webhooks/paypal")
async def paypal_webhook_endpoint(
    request: Request,
    session: Session = Depends(get_session),
    paypal_auth_algo: Optional[str] = Header(None, alias="paypal-auth-algo"),
    paypal_cert_url: Optional[str] = Header(None, alias="paypal-cert-url"),
    paypal_transmission_id: Optional[str] = Header(None, alias="paypal-transmission-id"),
    paypal_transmission_sig: Optional[str] = Header(None, alias="paypal-transmission-sig"),
    paypal_transmission_time: Optional[str] = Header(None, alias="paypal-transmission-time"),
):
    """Receive and verify PayPal webhook notifications."""
    body_bytes = await request.body()
    headers = {
        "paypal-auth-algo": paypal_auth_algo or "",
        "paypal-cert-url": paypal_cert_url or "",
        "paypal-transmission-id": paypal_transmission_id or "",
        "paypal-transmission-sig": paypal_transmission_sig or "",
        "paypal-transmission-time": paypal_transmission_time or "",
    }

    is_verified = await verify_webhook_signature(headers, body_bytes, settings.PAYPAL_WEBHOOK_ID)
    if not is_verified:
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")

    event_data = json.loads(body_bytes.decode("utf-8"))
    await process_webhook_event(session, event_data)
    return {"status": "success"}


# ==============================================================================
# Measurement API — shared by Studio & Agent
# ==============================================================================

@app.post("/api/measure")
async def api_measure(
    file: UploadFile = File(...),
    boxes: str = Form(...),
):
    """Measure swatches with white-paper lighting correction.

    Accepts multipart form: `file` (image) and `boxes` (JSON string):
    {"paper": [x0,y0,x1,y1], "swatches": [[x0,y0,x1,y1], ...]}
    Coordinates are fractions 0-1 of image width/height.
    """
    # Parse boxes JSON
    try:
        boxes_data = json.loads(boxes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in 'boxes' field.")

    paper_box_frac = boxes_data.get("paper")
    swatch_boxes_frac = boxes_data.get("swatches", [])

    if not paper_box_frac or len(paper_box_frac) != 4:
        raise HTTPException(status_code=400, detail="Paper box is required: [x0, y0, x1, y1] as fractions 0-1.")
    if not swatch_boxes_frac or len(swatch_boxes_frac) == 0:
        raise HTTPException(status_code=400, detail="At least one swatch box is required.")

    # Load image with Pillow
    contents = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(contents))
        pil_img = ImageOps.exif_transpose(pil_img)
        pil_img = pil_img.convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {e}")

    # Resize so long side is 1600 px
    w, h = pil_img.size
    long_side = max(w, h)
    if long_side > 1600:
        scale = 1600 / long_side
        pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = pil_img.size

    img_rgb = np.array(pil_img, dtype=np.uint8)

    # Convert fractional boxes to pixel coordinates
    def frac_to_px(box_frac):
        x0 = int(round(box_frac[0] * w))
        y0 = int(round(box_frac[1] * h))
        x1 = int(round(box_frac[2] * w))
        y1 = int(round(box_frac[3] * h))
        return [max(0, x0), max(0, y0), min(w, x1), min(h, y1)]

    paper_box = frac_to_px(paper_box_frac)

    # Validate paper box
    pw = paper_box[2] - paper_box[0]
    ph = paper_box[3] - paper_box[1]
    if pw < 10 or ph < 10:
        raise HTTPException(status_code=400, detail=f"Paper box too small: {pw}x{ph}px. Must be at least 10x10.")

    # White balance the full image
    balanced_img = white_balance(img_rgb, paper_box)

    # Compute paper stats for confidence
    paper_crop_raw = crop(img_rgb, paper_box).reshape(-1, 3)
    from skimage import color as skcolor
    paper_rgb_norm = paper_crop_raw.astype(np.float64) / 255.0
    paper_lab_pixels = skcolor.rgb2lab(paper_rgb_norm.reshape(-1, 1, 3)).reshape(-1, 3)
    paper_l_spread = float(np.std(paper_lab_pixels[:, 0]))
    raw_paper_l = float(np.median(paper_lab_pixels[:, 0]))

    results = []
    for i, sb_frac in enumerate(swatch_boxes_frac):
        if len(sb_frac) != 4:
            raise HTTPException(status_code=400, detail=f"Swatch box {i+1} must have 4 coordinates.")

        sbox = frac_to_px(sb_frac)
        sw_w = sbox[2] - sbox[0]
        sw_h = sbox[3] - sbox[1]
        if sw_w < 10 or sw_h < 10:
            raise HTTPException(status_code=400, detail=f"Swatch box {i+1} too small: {sw_w}x{sw_h}px. Must be at least 10x10.")

        # Corrected LAB (after white balance)
        corrected_lab = swatch_lab(balanced_img, sbox)
        L, a, b = float(corrected_lab[0]), float(corrected_lab[1]), float(corrected_lab[2])

        # Raw LAB (no white balance) for before/after
        raw_lin = srgb_to_linear(img_rgb.astype(np.float64))
        raw_lab = swatch_lab(raw_lin, sbox)
        raw_hex = lab_to_hex(raw_lab.tolist())

        corrected_hex = lab_to_hex([L, a, b])
        chroma = float(math.sqrt(a**2 + b**2))
        hue_deg = float(math.degrees(math.atan2(b, a))) % 360.0
        ita_deg = calculate_ita(L, b)
        depth = depth_from_ita(ita_deg)
        undertone = undertone_from_hue(hue_deg)

        # Compute confidence
        swatch_crop = crop(img_rgb, sbox).reshape(-1, 3)
        glare_ratio = float(np.mean(swatch_crop.max(axis=1) >= 250))
        swatch_rgb_norm = swatch_crop.astype(np.float64) / 255.0
        swatch_lab_pixels = skcolor.rgb2lab(swatch_rgb_norm.reshape(-1, 1, 3)).reshape(-1, 3)
        swatch_l_spread = float(np.std(swatch_lab_pixels[:, 0]))

        confidence = compute_confidence(
            paper_l_spread=paper_l_spread,
            swatch_glare_ratio=glare_ratio,
            swatch_l_spread=swatch_l_spread,
            raw_paper_l=raw_paper_l,
        )

        results.append({
            "swatch_index": i,
            "corrected": {
                "lab": [round(L, 2), round(a, 2), round(b, 2)],
                "hex": corrected_hex,
                "chroma": round(chroma, 2),
                "hue_deg": round(hue_deg, 2),
                "ita_deg": round(ita_deg, 2),
                "depth": depth,
                "undertone": undertone,
            },
            "raw_hex": raw_hex,
            "confidence": confidence,
        })

    return {"swatches": results}


# ==============================================================================
# References API — shopper saves measured shade to DB
# ==============================================================================

@app.post("/api/references")
async def api_create_reference(
    payload: Dict[str, Any],
    session: Session = Depends(get_session),
):
    """Create a BuyerReference from measured CIELAB values and return a REF-XXXXXX code."""
    lab = payload.get("lab")
    hex_color = payload.get("hex")

    if not lab or len(lab) != 3:
        raise HTTPException(status_code=400, detail="Lab values [L, a, b] are required.")

    L, a, b = float(lab[0]), float(lab[1]), float(lab[2])
    if not hex_color:
        hex_color = lab_to_hex([L, a, b])

    ref_code = f"REF-{uuid.uuid4().hex[:6].upper()}"
    confidence = int(payload.get("confidence", 90))

    buyer_ref = BuyerReference(
        ref_code=ref_code,
        L=round(L, 2),
        a=round(a, 2),
        b=round(b, 2),
        hex=hex_color,
        confidence=confidence,
    )
    session.add(buyer_ref)
    session.commit()

    return {
        "ref_code": ref_code,
        "hex": hex_color,
        "lab": [round(L, 2), round(a, 2), round(b, 2)],
    }


# ==============================================================================
# Shades API — seller publishes measured shades to catalog
# ==============================================================================

@app.post("/api/shades")
async def api_create_shades(
    payload: Dict[str, Any],
    session: Session = Depends(get_session),
):
    """Publish one or more measured swatches as Shade rows in the catalog."""
    swatches = payload.get("swatches", [])
    if not swatches:
        raise HTTPException(status_code=400, detail="At least one swatch is required.")

    product_id = payload.get("product_id")
    if not product_id:
        # Default to first product
        first_product = session.exec(select(Product)).first()
        if not first_product:
            raise HTTPException(status_code=400, detail="No products exist. Create a product first.")
        product_id = first_product.id

    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=400, detail=f"Unknown product_id: {product_id}")

    created_ids = []
    for sw in swatches:
        shade_name = sw.get("shade_name")
        if not shade_name:
            raise HTTPException(status_code=400, detail="Each swatch must have a shade_name.")

        lab = sw.get("lab", [0, 0, 0])
        L, a, b = float(lab[0]), float(lab[1]), float(lab[2])
        hex_color = sw.get("hex") or lab_to_hex([L, a, b])
        chroma = float(sw.get("chroma", math.sqrt(a**2 + b**2)))
        hue_deg = float(sw.get("hue_deg", math.degrees(math.atan2(b, a)) % 360.0))
        ita_deg = float(sw.get("ita_deg", calculate_ita(L, b)))
        depth = sw.get("depth") or depth_from_ita(ita_deg)
        undertone = sw.get("undertone") or undertone_from_hue(hue_deg)
        confidence = int(sw.get("confidence", 90))

        shade_id = f"shd_{uuid.uuid4().hex[:8]}"
        shade = Shade(
            id=shade_id,
            product_id=product_id,
            shade_name=shade_name,
            hex=hex_color,
            L=round(L, 2),
            a=round(a, 2),
            b=round(b, 2),
            chroma=round(chroma, 2),
            hue_deg=round(hue_deg, 2),
            ita_deg=round(ita_deg, 2),
            depth=depth,
            undertone=undertone,
            confidence=confidence,
            source="measured",
        )
        session.add(shade)
        session.flush()

        # Generate and store passport
        passport = create_shade_passport_dict(
            shade_id=shade.id,
            product_id=product.id,
            product_name=product.name,
            category=product.category,
            price_usd=product.price_usd,
            shade_name=shade.shade_name,
            hex_color=shade.hex,
            lab=[shade.L, shade.a, shade.b],
            chroma=shade.chroma,
            hue_deg=shade.hue_deg,
            ita_deg=shade.ita_deg,
            depth=shade.depth,
            undertone=shade.undertone,
            confidence=shade.confidence,
            measured_at=shade.measured_at.isoformat(),
            method_reference="white paper",
        )
        p_hash, p_sig = sign_passport(passport)
        shade.passport_hash = p_hash
        shade.passport_sig = p_sig
        session.add(shade)

        created_ids.append(shade_id)

    session.commit()
    return {"created": created_ids}


@app.delete("/api/shades/{shade_id}")
async def api_delete_shade(shade_id: str, session: Session = Depends(get_session)):
    """Delete a measured shade from the catalog. Only measured shades can be deleted."""
    shade = session.get(Shade, shade_id)
    if not shade:
        raise HTTPException(status_code=404, detail="Shade not found.")
    if getattr(shade, "source", "seed") != "measured":
        raise HTTPException(status_code=400, detail="Cannot delete seeded shades.")
    session.delete(shade)
    session.commit()
    return {"deleted": shade_id}


@app.get("/api/shades")
def api_list_shades(session: Session = Depends(get_session)):
    """List all shades in the catalog."""
    shades = session.exec(select(Shade)).all()
    return [
        {
            "id": s.id,
            "shade_name": s.shade_name,
            "hex": s.hex,
            "L": s.L,
            "a": s.a,
            "b": s.b,
            "depth": s.depth,
            "undertone": s.undertone,
            "confidence": s.confidence,
            "source": getattr(s, "source", "seed"),
            "product_id": s.product_id,
            "passport_hash": s.passport_hash,
        }
        for s in shades
    ]


# ==============================================================================
# Interactive API Endpoints for Frontend & MCP Agents
# ==============================================================================

@app.post("/api/agent/message")
async def api_agent_message(payload: Dict[str, Any], session: Session = Depends(get_session)):
    """Conversational endpoint for the web buyer agent."""
    user_message = payload.get("message", "")
    history = payload.get("history", [])
    ref_code = payload.get("reference_code")
    turn_res = await run_agent_turn(
        session=session,
        user_message=user_message,
        conversation_history=history,
        reference_code=ref_code,
    )
    return turn_res


@app.post("/api/demo/reset")
def api_demo_reset(session: Session = Depends(get_session)):
    """Reset database to initial pristine state for hackathon judges."""
    from app.db import seed_db
    from sqlmodel import delete
    session.exec(delete(PromiseClaim))
    session.exec(delete(Order))
    # Delete measured shades but keep seeded ones
    session.exec(delete(Shade).where(Shade.source == "measured"))
    # Delete buyer references except the sample one
    session.exec(delete(BuyerReference).where(BuyerReference.ref_code != "REF-SAMPLE"))
    session.commit()
    # Re-seed if needed
    seed_db(session)
    return {"status": "reset_complete"}
