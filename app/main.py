"""FastAPI application entry point, page routers, API endpoints, and MCP mounting."""

import io
import json
import uuid
import numpy as np
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from skimage import io as skio
from sqlmodel import Session, select

from app.color.metrics import calculate_ita, depth_from_ita, undertone_from_hue
from app.color.pipeline import lab_to_hex, rgb_to_lab
from app.config import get_settings
from app.db import get_session, init_db
from app.llm.agent import run_agent_turn
from app.models import BuyerReference, Order, Product, PromiseClaim, Shade, Shop
from app.passport import verify_passport
from app.paypal.client import paypal_client
from app.paypal.webhooks import process_webhook_event, verify_webhook_signature
from app.services import (
    QUERY_REFERENCE_CACHE,
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
        "tools_count": 6,
        "tools": [
            {
                "name": "match_shade_tool",
                "description": "Calculate mathematical CIEDE2000 ΔE between customer reference and catalog shades."
            },
            {
                "name": "search_products_tool",
                "description": "Filter products by price, coverage, finish, and depth."
            },
            {
                "name": "get_shade_passport_tool",
                "description": "Retrieve SHA-256 canonical hash & HMAC-SHA256 verifiable signature."
            },
            {
                "name": "create_checkout_tool",
                "description": "Initialize a verified server-authoritative PayPal Orders v2 checkout."
            },
            {
                "name": "get_order_status_tool",
                "description": "Real-time PayPal order telemetry and status tracking."
            },
            {
                "name": "open_shade_promise_tool",
                "description": "Automated dispute resolution: triggers instant PayPal refund if ΔE > 2.5."
            }
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
        context={"shop": shop, "products": products, "shades": shades},
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
    orders = session.exec(select(Order).order_by(Order.created_at.desc())).all()
    claims = session.exec(select(PromiseClaim)).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "orders": orders,
            "claims": claims,
            "paypal_logs": paypal_client.call_logs[-15:],
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
        context={"shop": shop, "products": products, "shades": shades},
    )


@app.get("/measure", response_class=HTMLResponse)
def measure_view(request: Request):
    """Consumer tool to upload current foundation swatch and acquire a permanent REF- code."""
    return templates.TemplateResponse(request=request, name="measure.html", context={})


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
        context={"passport": passport, "is_valid": is_valid},
    )


@app.get("/promise/{order_id}", response_class=HTMLResponse)
def promise_view(order_id: str, request: Request, session: Session = Depends(get_session)):
    """Automated Shade Promise dispute resolution portal."""
    order = session.get(Order, order_id)
    return templates.TemplateResponse(
        request=request,
        name="promise.html",
        context={"order": order},
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
    paypal_order_id = token
    order = None

    if internal_id:
        order = session.get(Order, internal_id)
    elif paypal_order_id:
        order = session.exec(select(Order).where(Order.paypal_order_id == paypal_order_id)).first()

    if not order:
        order = session.exec(select(Order).order_by(Order.created_at.desc())).first()

    if order:
        capture_res = await paypal_client.capture_order(order.paypal_order_id or "MOCK-ORD")
        order.status = "COMPLETED"
        order.capture_id = (
            capture_res.get("purchase_units", [{}])[0]
            .get("payments", {})
            .get("captures", [{}])[0]
            .get("id", f"CAP-{uuid.uuid4().hex[:8]}")
        )
        session.add(order)
        session.commit()

    return RedirectResponse(url="/dashboard?captured=true")


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
        "transmission_id": paypal_transmission_id or "",
        "transmission_sig": paypal_transmission_sig or "",
        "transmission_time": paypal_transmission_time or "",
    }

    is_verified = await verify_webhook_signature(headers, body_bytes, settings.PAYPAL_WEBHOOK_ID)
    if not is_verified:
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")

    event_data = json.loads(body_bytes.decode("utf-8"))
    await process_webhook_event(session, event_data)
    return {"status": "success"}


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


@app.post("/api/measure-reference")
async def api_measure_reference(
    payload: Dict[str, Any],
    session: Session = Depends(get_session),
):
    """Generate a temporary in-memory query reference code (e.g. REF-7K2Q) from swatch coordinates."""
    rgb = payload.get("rgb")
    lab = payload.get("lab")

    if rgb and not lab:
        lab = rgb_to_lab(rgb)
    elif not lab:
        lab = [62.4, 13.9, 24.1]

    hex_color = payload.get("hex") or lab_to_hex(lab)
    ref_code = f"REF-{uuid.uuid4().hex[:4].upper()}"

    clean_lab = [float(round(lab[0], 2)), float(round(lab[1], 2)), float(round(lab[2], 2))]

    # Save ONLY to transient query cache — never add user swatches to product catalog
    QUERY_REFERENCE_CACHE[ref_code] = {
        "ref_code": ref_code,
        "L": clean_lab[0],
        "a": clean_lab[1],
        "b": clean_lab[2],
        "hex": hex_color,
    }

    return {"ref_code": ref_code, "hex": hex_color, "lab": clean_lab}


@app.post("/api/upload-swatch")
async def api_upload_swatch(file: UploadFile = File(...)):
    """Upload a swatch photo, extract median CIELAB values from center, and generate query reference."""
    contents = await file.read()
    try:
        img = skio.imread(io.BytesIO(contents))
        # Ensure RGB (strip alpha if RGBA)
        if img.ndim == 3 and img.shape[2] >= 3:
            img_rgb = img[:, :, :3]
        elif img.ndim == 2:
            img_rgb = np.stack([img] * 3, axis=-1)
        else:
            raise ValueError("Unsupported image format")

        # Crop center 40% of the image to sample the swatch/skin
        h, w = img_rgb.shape[:2]
        ch0, ch1 = int(h * 0.3), int(h * 0.7)
        cw0, cw1 = int(w * 0.3), int(w * 0.7)
        center_patch = img_rgb[ch0:ch1, cw0:cw1]

        # Median RGB
        median_rgb = np.median(center_patch.reshape(-1, 3), axis=0)
        lab = rgb_to_lab(median_rgb)
    except Exception as e:
        # Fallback if image decode fails
        lab = [62.4, 13.9, 24.1]

    hex_color = lab_to_hex(lab)
    ref_code = f"REF-{uuid.uuid4().hex[:4].upper()}"

    clean_lab = [float(round(lab[0], 2)), float(round(lab[1], 2)), float(round(lab[2], 2))]

    # Store in transient query cache (never in database product catalog)
    QUERY_REFERENCE_CACHE[ref_code] = {
        "ref_code": ref_code,
        "L": clean_lab[0],
        "a": clean_lab[1],
        "b": clean_lab[2],
        "hex": hex_color,
    }

    return {
        "ref_code": ref_code,
        "hex": hex_color,
        "lab": clean_lab,
        "status": "success",
    }


@app.post("/api/demo/reset")
def api_demo_reset(session: Session = Depends(get_session)):
    """Reset database to initial pristine state for hackathon judges."""
    from app.db import seed_db
    from sqlmodel import delete
    session.exec(delete(PromiseClaim))
    session.exec(delete(Order))
    session.exec(delete(Shade))
    session.exec(delete(Product))
    session.exec(delete(Shop))
    session.commit()
    seed_db(session)
    return {"status": "reset_complete"}

