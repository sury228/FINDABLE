"""FastMCP server exposing Findable tools over streamable HTTP for Claude Desktop and AI agents."""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from app.db import engine
from app.services import (
    create_checkout,
    get_order_status,
    get_shade_passport_service,
    match_shade,
    open_shade_promise,
    search_products,
)

# Initialize FastMCP Server
mcp = FastMCP("Findable Shade Matcher")


@mcp.tool()
def search_products_tool(
    query: Optional[str] = None,
    category: Optional[str] = "foundation",
    max_price: Optional[float] = None,
    undertone: Optional[str] = None,
    depth: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Search available cosmetic products with verified Shade Passports.

    Quote delta_e and undertone when recommending a shade; do not invent colour claims.
    """
    with Session(engine) as session:
        return search_products(
            session=session,
            query=query,
            category=category,
            max_price=max_price,
            undertone=undertone,
            depth=depth,
            limit=limit,
        )


@mcp.tool()
def match_shade_tool(
    reference: str,
    category: Optional[str] = "foundation",
    max_price: Optional[float] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Find closest matching shades based on measured CIELAB ΔE and undertone alignment.

    Reference can be a REF- code (e.g. REF-7K2Q), hexadecimal color (#C08C6C), or raw coordinates.
    Quote delta_e and undertone when recommending a shade; do not invent colour claims.
    """
    with Session(engine) as session:
        return match_shade(
            session=session,
            reference=reference,
            category=category,
            max_price=max_price,
            limit=limit,
        )


@mcp.tool()
def get_shade_passport_tool(shade_id: str) -> Dict[str, Any]:
    """Retrieve the cryptographically signed Shade Passport JSON for a given shade.

    Allows an AI agent to verify the canonical SHA-256 hash, HMAC signature, and physical CIELAB coordinates.
    """
    with Session(engine) as session:
        passport = get_shade_passport_service(session, shade_id)
        return passport or {"error": f"Shade '{shade_id}' not found"}


@mcp.tool()
async def create_checkout_tool(
    items: List[Dict[str, Any]],
    agent_name: str = "claude-desktop",
) -> Dict[str, Any]:
    """Initialize a verified PayPal checkout order for the chosen items.

    Always show the shopper the approve_url. Payment happens only when they approve it in PayPal.
    """
    with Session(engine) as session:
        return await create_checkout(
            session=session,
            items=items,
            agent_name=agent_name,
        )


@mcp.tool()
async def get_order_status_tool(order_id: str) -> Dict[str, Any]:
    """Check the real-time status of a PayPal order.

    Never say an order is paid until get_order_status returns COMPLETED.
    """
    with Session(engine) as session:
        return await get_order_status(session, order_id)


@mcp.tool()
async def open_shade_promise_tool(
    order_id: str,
    shade_id: str,
    ref_code: str,
) -> Dict[str, Any]:
    """Initiate an automated Shade Promise dispute resolution and instant refund.

    Re-measures the delivered product against the customer's reference code and triggers a PayPal refund if ΔE > 2.5.
    """
    with Session(engine) as session:
        return await open_shade_promise(
            session=session,
            order_id=order_id,
            shade_id=shade_id,
            ref_code=ref_code,
        )


if __name__ == "__main__":
    mcp.run()

