"""Shopper conversational agent loop with zero-quota fallback and tool routing."""

import json
import re
from typing import Any, Dict, List, Optional
from sqlmodel import Session

from app.llm.client import LLMClient
from app.services import (
    create_checkout,
    get_order_status,
    match_shade,
    search_products,
)


async def run_agent_turn(
    session: Session,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    reference_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one turn of the buyer agent.

    Parses user intent, executes deterministic backend tools (match_shade, search_products, create_checkout),
    and formats human and structured tool responses without requiring external LLM tokens when offline.
    """
    client = LLMClient()
    user_lower = user_message.lower()

    # Rule-based zero-quota fallback matching
    ref_match = re.search(r"\b(REF-[A-Z0-9]{4,8})\b", user_message, re.IGNORECASE)
    detected_ref = reference_code or (ref_match.group(1).upper() if ref_match else None)

    # Extract price filter from message (e.g. "under $30", "below $25")
    price_match = re.search(r"(?:under|below|max|less than)\s*\$?\s*(\d+(?:\.\d+)?)", user_lower)
    max_price = float(price_match.group(1)) if price_match else None

    tools_called = []
    cards = []

    # 1. Checkout intent
    if "buy" in user_lower or "checkout" in user_lower or "order" in user_lower:
        shade_match = re.search(r"\b(shd_[a-z0-9_]+)\b", user_message, re.IGNORECASE)
        if not shade_match:
            # Ask which shade — never default
            reply = (
                "Which shade would you like to order? "
                "Please specify a shade ID (e.g. `shd_honey04`) or first ask me to match your shade "
                "by uploading a swatch photo with the 📷 button."
            )
            return {"reply": reply, "tools_called": [], "cards": []}

        shade_id = shade_match.group(1)
        tools_called.append({
            "tool": "create_checkout",
            "args": {"items": [{"shade_id": shade_id, "quantity": 1}], "agent_name": "findable-web-agent"},
        })
        try:
            checkout_res = await create_checkout(
                session=session,
                items=[{"shade_id": shade_id, "quantity": 1}],
                agent_name="findable-web-agent",
            )
        except ValueError as e:
            return {"reply": str(e), "tools_called": tools_called, "cards": []}

        cards.append({
            "type": "checkout",
            "data": checkout_res,
        })
        reply = (
            f"I have initialized a verified PayPal checkout for your match. "
            f"Your order total is ${checkout_res['total']:.2f} {checkout_res['currency']}. "
            f"Please approve payment using the button below. I will not confirm payment until verified."
        )

    # 2. Matching intent (with reference code or keyword)
    elif detected_ref or "match" in user_lower or "shade" in user_lower or "foundation" in user_lower:
        if not detected_ref:
            # Ask to upload a swatch — never use a default reference
            reply = (
                "I need your shade reference to find a match. "
                "Please upload a swatch photo using the 📷 button below, "
                "or paste your reference code (e.g. `REF-7K2Q`) if you already have one."
            )
            return {"reply": reply, "tools_called": [], "cards": []}

        active_ref = detected_ref
        tools_called.append({
            "tool": "match_shade",
            "args": {"reference": active_ref, "max_price": max_price, "limit": 5},
        })

        try:
            matches = match_shade(session=session, reference=active_ref, max_price=max_price, limit=5)
        except ValueError as e:
            return {"reply": str(e), "tools_called": tools_called, "cards": []}

        cards.append({
            "type": "matches",
            "data": matches,
            "reference_code": active_ref,
        })

        if matches:
            top = matches[0]
            price_note = f" under ${max_price:.0f}" if max_price else ""
            de = top['delta_e']

            if de <= 2.0:
                match_status = "**Hard to tell apart** — this shade is very close to your measured skin tone."
            elif de <= 4.0:
                match_status = "**Close match found** — wearable shade, minor tone difference."
            else:
                match_status = "**Different shade** — no close match in the current catalog. Showing nearest candidates."

            reply = (
                f"{match_status}\n\n"
                f"Based on your measured reference **{active_ref}**{price_note}, "
                f"I ranked **{len(matches)} candidate(s)** from the catalogue by CIEDE2000 optical distance.\n\n"
                f"Top candidate: **{top['shade_name']}** from *{top['product_name']}* — "
                f"**ΔE {de:.1f}** ({top['explanation']}), "
                f"**${top['price']:.2f} USD**, undertone: {'matched ✓' if top.get('undertone_match') else 'nearby'}.\n\n"
                f"Click **Order Shade** to purchase with PayPal."
            )
        else:
            reply = "I couldn't find a shade match meeting that criteria. Try adjusting the price filter or reference."

    # 3. Product search intent
    else:
        tools_called.append({
            "tool": "search_products",
            "args": {"query": user_message, "limit": 5},
        })
        results = search_products(session=session, query=user_message, limit=5)
        cards.append({
            "type": "products",
            "data": results,
        })
        reply = (
            f"I explored the catalogue and found {len(results)} product line(s) with calibrated Shade Passports. "
            f"Upload a swatch photo with the 📷 button to find your shade match!"
        )

    return {
        "reply": reply,
        "tools_called": tools_called,
        "cards": cards,
    }
