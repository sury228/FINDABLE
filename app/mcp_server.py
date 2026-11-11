"""MCP server exposing Findable tools over streamable HTTP for Claude Desktop and AI agents."""

from typing import Any, Dict, List, Optional
try:
    from mcp.server import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from app.db import engine
from app.services import (
    create_checkout as svc_create_checkout,
    get_order_status as svc_get_order_status,
    get_shade_passport_service as svc_get_shade_passport_service,
    match_shade as svc_match_shade,
    search_products as svc_search_products,
)

# Initialize MCP Server
mcp = FastMCP("Findable Shade Matcher")


@mcp.tool()
def search_products(
    query: Optional[str] = None,
    category: Optional[str] = "foundation",
    max_price: Optional[float] = None,
    undertone: Optional[str] = None,
    depth: Optional[str] = None,
    limit: int = 5,
) -> Any:
    """Search available cosmetic products with verified Shade Passports.

    Quote delta_e and undertone when recommending a shade; do not invent colour claims.
    """
    try:
        with Session(engine) as session:
            return svc_search_products(
                session=session,
                query=query,
                category=category,
                max_price=max_price,
                undertone=undertone,
                depth=depth,
                limit=limit,
            )
    except Exception as e:
        return f"Error searching products: {e}"


@mcp.tool()
def match_shade(
    reference: str,
    category: Optional[str] = "foundation",
    max_price: Optional[float] = None,
    limit: int = 5,
) -> Any:
    """Find closest matching shades based on measured CIELAB ΔE and undertone alignment.

    Reference can be a REF- code (e.g. REF-7K2Q), hexadecimal color (#C08C6C), or raw coordinates.
    Quote delta_e and undertone when recommending a shade; do not invent colour claims.
    """
    try:
        with Session(engine) as session:
            return svc_match_shade(
                session=session,
                reference=reference,
                category=category,
                max_price=max_price,
                limit=limit,
            )
    except Exception as e:
        return f"Error matching shade: {e}"


@mcp.tool()
def get_shade_passport(shade_id: str) -> Any:
    """Retrieve the cryptographically signed Shade Passport JSON for a given shade.

    Allows an AI agent to verify the canonical SHA-256 hash, HMAC signature, and physical CIELAB coordinates.
    """
    try:
        with Session(engine) as session:
            passport = svc_get_shade_passport_service(session, shade_id)
            if not passport:
                return f"Error: Shade '{shade_id}' not found in catalog."
            return passport
    except Exception as e:
        return f"Error retrieving passport: {e}"


@mcp.tool()
async def create_checkout(
    items: List[Dict[str, Any]],
    agent_name: str = "claude-desktop",
) -> Any:
    """Initialize a verified PayPal checkout order for the chosen items.

    Always show the shopper the approve_url. Payment happens only when they approve it in PayPal.
    """
    try:
        with Session(engine) as session:
            return await svc_create_checkout(
                session=session,
                items=items,
                agent_name=agent_name,
            )
    except Exception as e:
        return f"Error creating checkout: {e}"


@mcp.tool()
async def get_order_status(order_id: str) -> Any:
    """Check the real-time status of a PayPal order.

    Never say an order is paid until get_order_status returns COMPLETED.
    """
    try:
        with Session(engine) as session:
            return await svc_get_order_status(session, order_id)
    except Exception as e:
        return f"Error checking order status: {e}"


if __name__ == "__main__":
    mcp.run()
