"""Shopper conversational agent loop with Groq tool-calling and rule-based fallback."""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlmodel import Session

from app.config import get_settings
from app.services import (
    create_checkout,
    get_order_status,
    get_shade_passport_service,
    match_shade,
    search_products,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Findable's AI Shopping Agent.
You assist shoppers in discovering foundation and beauty products matching their calibrated skin tone.

RULES:
1. Quote delta_e and undertone strictly from tool results. NEVER invent or hallucinate colour claims or accuracy numbers.
2. If the user wants to match a shade but hasn't provided a reference (REF-XXXX code, [L,a,b] coordinates, or hex), ask them to upload a swatch photo using the 📷 button.
3. When recommending or ordering a shade, always show the approve link from the checkout tool.
4. NEVER claim an order is paid until get_order_status returns status COMPLETED.
5. If the user says "buy" or "order" without specifying a shade ID, ask which shade they want to order.
6. Speak concisely, helpful, and professionally.
"""

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search available cosmetic products in the catalog by keyword, category, price, undertone, or depth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword search across product name and description"},
                    "category": {"type": "string", "description": "Product category e.g. foundation"},
                    "max_price": {"type": "number", "description": "Maximum price in USD"},
                    "undertone": {"type": "string", "description": "Undertone: warm, neutral, cool"},
                    "depth": {"type": "string", "description": "Depth bucket: very light, light, medium, tan, deep, rich"},
                    "limit": {"type": "integer", "description": "Max results to return, default 5"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "match_shade",
            "description": "Calculate mathematical CIEDE2000 ΔE between a customer reference (REF-XXXX code, [L,a,b] array, or hex #RRGGBB) and catalog shades.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string", "description": "Reference identifier: REF code (e.g. REF-7K2Q), hex color (#C08C6C), or comma-separated LAB"},
                    "category": {"type": "string", "description": "Filter by product category e.g. foundation"},
                    "max_price": {"type": "number", "description": "Maximum price in USD"},
                    "limit": {"type": "integer", "description": "Max top matches to return (default 5)"}
                },
                "required": ["reference"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_shade_passport",
            "description": "Retrieve cryptographic SHA-256 canonical hash & HMAC-SHA256 signature for a catalog shade.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shade_id": {"type": "string", "description": "Catalog shade ID e.g. shd_honey04"}
                },
                "required": ["shade_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_checkout",
            "description": "Initialize a verified server-authoritative PayPal Orders v2 checkout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shade_id": {"type": "string", "description": "Catalog shade ID to purchase e.g. shd_honey04"},
                    "quantity": {"type": "integer", "description": "Quantity to purchase (default 1)"}
                },
                "required": ["shade_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Check real-time status and PayPal payment capture of an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Internal order ID or PayPal order ID"}
                },
                "required": ["order_id"]
            }
        }
    }
]


async def _execute_tool(name: str, args: Dict[str, Any], session: Session) -> Any:
    """Execute domain tools with session dependency."""
    if name == "search_products":
        return search_products(
            session=session,
            query=args.get("query"),
            category=args.get("category"),
            max_price=args.get("max_price"),
            undertone=args.get("undertone"),
            depth=args.get("depth"),
            limit=args.get("limit", 5),
        )
    elif name == "match_shade":
        ref = args.get("reference")
        # Handle comma-separated list of lab strings e.g. "62.4,13.9,24.1"
        if isinstance(ref, str) and "," in ref:
            try:
                ref = [float(x.strip()) for x in ref.split(",")]
            except Exception:
                pass
        return match_shade(
            session=session,
            reference=ref,
            category=args.get("category"),
            max_price=args.get("max_price"),
            limit=args.get("limit", 5),
        )
    elif name == "get_shade_passport":
        return get_shade_passport_service(session=session, shade_id=args.get("shade_id"))
    elif name == "create_checkout":
        shade_id = args.get("shade_id")
        quantity = args.get("quantity", 1)
        return await create_checkout(
            session=session,
            items=[{"shade_id": shade_id, "quantity": quantity}],
            agent_name="findable-groq-agent",
        )
    elif name == "get_order_status":
        return await get_order_status(session=session, order_id=args.get("order_id"))
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _run_llm_turn(
    session: Session,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    api_key: str,
    model: str,
) -> Optional[Dict[str, Any]]:
    """Execute conversational turn using Groq with tool-calling loop (up to 5 rounds)."""
    from groq import AsyncGroq

    client = AsyncGroq(api_key=api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in conversation_history[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    tools_called = []
    cards = []

    for _ in range(5):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=800,
            )
        except Exception as e:
            logger.warning("Groq API call failed: %s", e)
            return None

        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            })

            for tc in msg.tool_calls:
                func_name = tc.function.name
                try:
                    func_args = json.loads(tc.function.arguments)
                except Exception:
                    func_args = {}

                tools_called.append({
                    "tool": func_name,
                    "args": func_args,
                })

                try:
                    tool_result = await _execute_tool(func_name, func_args, session)
                except Exception as ex:
                    tool_result = {"error": str(ex)}

                # Add UI cards for match and checkout results
                if func_name == "match_shade" and isinstance(tool_result, list):
                    cards.append({
                        "type": "matches",
                        "data": tool_result,
                        "reference_code": func_args.get("reference", ""),
                    })
                elif func_name == "create_checkout" and isinstance(tool_result, dict) and "approve_url" in tool_result:
                    cards.append({
                        "type": "checkout",
                        "data": tool_result,
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result),
                })
        else:
            # Final text response
            reply = msg.content or "I have processed your request."
            return {
                "reply": reply,
                "tools_called": tools_called,
                "cards": cards,
                "mode": "llm",
            }

    # If looped 5 times
    return {
        "reply": "I've completed evaluating your request.",
        "tools_called": tools_called,
        "cards": cards,
        "mode": "llm",
    }


def _run_rule_turn(
    session: Session,
    user_message: str,
    reference_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministic zero-quota regex fallback."""
    user_lower = user_message.lower()

    ref_match = re.search(r"\b(REF-[A-Z0-9]{4,8})\b", user_message, re.IGNORECASE)
    detected_ref = reference_code or (ref_match.group(1).upper() if ref_match else None)

    price_match = re.search(r"(?:under|below|max|less than)\s*\$?\s*(\d+(?:\.\d+)?)", user_lower)
    max_price = float(price_match.group(1)) if price_match else None

    tools_called = []
    cards = []

    # 1. Checkout intent
    if "buy" in user_lower or "checkout" in user_lower or "order" in user_lower:
        shade_match = re.search(r"\b(shd_[a-z0-9_]+)\b", user_message, re.IGNORECASE)
        if not shade_match:
            reply = (
                "Which shade would you like to order? "
                "Please specify a shade ID (e.g. `shd_honey04`) or first ask me to match your shade "
                "by uploading a swatch photo with the 📷 button."
            )
            return {"reply": reply, "tools_called": [], "cards": [], "mode": "rules"}

        shade_id = shade_match.group(1)
        tools_called.append({
            "tool": "create_checkout",
            "args": {"shade_id": shade_id, "quantity": 1},
        })
        try:
            from app.paypal.client import paypal_client
            # Synchronous wrapper in rule turn
            import asyncio
            checkout_res = asyncio.run(create_checkout(
                session=session,
                items=[{"shade_id": shade_id, "quantity": 1}],
                agent_name="findable-web-agent",
            ))
        except Exception as e:
            return {"reply": str(e), "tools_called": tools_called, "cards": [], "mode": "rules"}

        cards.append({
            "type": "checkout",
            "data": checkout_res,
        })
        reply = (
            f"I have initialized a verified PayPal checkout for your match. "
            f"Your order total is ${checkout_res['total']:.2f} {checkout_res['currency']}. "
            f"Please approve payment using the button below. I will not confirm payment until verified."
        )

    # 2. Matching intent
    elif detected_ref or "match" in user_lower or "shade" in user_lower or "foundation" in user_lower:
        if not detected_ref:
            reply = (
                "I need your shade reference to find a match. "
                "Please upload a swatch photo using the 📷 button below, "
                "or paste your reference code (e.g. `REF-7K2Q`) if you already have one."
            )
            return {"reply": reply, "tools_called": [], "cards": [], "mode": "rules"}

        active_ref = detected_ref
        tools_called.append({
            "tool": "match_shade",
            "args": {"reference": active_ref, "max_price": max_price, "limit": 5},
        })

        try:
            matches = match_shade(session=session, reference=active_ref, max_price=max_price, limit=5)
        except ValueError as e:
            return {"reply": str(e), "tools_called": tools_called, "cards": [], "mode": "rules"}

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
        "mode": "rules",
    }


async def run_agent_turn(
    session: Session,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    reference_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute one turn of the buyer agent. Uses Groq LLM if key is present, otherwise falls back to rules."""
    settings = get_settings()
    history = conversation_history or []

    # If Groq API key is present, attempt LLM call with tools
    if settings.LLM_API_KEY and settings.LLM_API_KEY.strip():
        llm_res = await _run_llm_turn(
            session=session,
            user_message=user_message,
            conversation_history=history,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL or "llama-3.3-70b-versatile",
        )
        if llm_res is not None:
            return llm_res

    # Fallback to rule engine
    return _run_rule_turn(
        session=session,
        user_message=user_message,
        reference_code=reference_code,
    )
