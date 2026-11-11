"""Cryptographic Shade Passport generation, canonical hashing, and HMAC signing."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from app.config import get_settings

settings = get_settings()


def canonical_json(data: Dict[str, Any]) -> str:
    """Serialize dictionary to deterministic canonical JSON with sorted keys and no whitespace."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def create_shade_passport_dict(
    shade_id: str,
    product_id: str,
    product_name: str,
    category: str,
    price_usd: float,
    shade_name: str,
    hex_color: str,
    lab: List[float],
    chroma: float,
    hue_deg: float,
    ita_deg: float,
    depth: str,
    undertone: str,
    confidence: int,
    measured_at: str = None,
    method_reference: str = "white paper",
) -> Dict[str, Any]:
    """Construct standard Shade Passport dictionary structure."""
    if measured_at is None:
        measured_at = datetime.now(timezone.utc).isoformat()

    passport_data: Dict[str, Any] = {
        "passport_version": "1.0",
        "shade_id": shade_id,
        "product": {
            "id": product_id,
            "name": product_name,
            "category": category,
            "price": {"value": f"{price_usd:.2f}", "currency": "USD"},
        },
        "shade_name": shade_name,
        "measured": {
            "hex": hex_color,
            "lab": [round(float(v), 2) for v in lab],
            "chroma": round(float(chroma), 2),
            "hue_deg": round(float(hue_deg), 2),
            "ita_deg": round(float(ita_deg), 2),
        },
        "labels": {
            "depth": depth,
            "undertone": undertone,
        },
        "confidence": confidence,
        "method": {
            "reference": method_reference,
            "illuminant": "D65",
            "delta_e": "CIEDE2000",
            "pipeline": "findable-color 0.1",
        },
        "measured_at": measured_at,
    }
    return passport_data


def sign_passport(passport_data: Dict[str, Any], secret: str = None) -> Tuple[str, str]:
    """Compute SHA-256 hash of canonical JSON and HMAC-SHA256 signature.

    Returns:
        (hash_str, signature_str)
    """
    if secret is None:
        secret = settings.PASSPORT_SECRET

    clean_data = {k: v for k, v in passport_data.items() if k not in ("hash", "signature")}
    serialized = canonical_json(clean_data).encode("utf-8")

    digest = hashlib.sha256(serialized).hexdigest()
    hash_str = f"sha256:{digest}"

    signature_digest = hmac.new(
        secret.encode("utf-8"),
        hash_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    sig_str = f"hmac-sha256:{signature_digest}"

    return hash_str, sig_str


def verify_passport(passport_data: Dict[str, Any], secret: str = None) -> bool:
    """Verify that a Shade Passport's hash and HMAC signature are valid and unmodified."""
    if secret is None:
        secret = settings.PASSPORT_SECRET

    recorded_hash = passport_data.get("hash")
    recorded_sig = passport_data.get("signature")

    if not recorded_hash or not recorded_sig:
        return False

    computed_hash, computed_sig = sign_passport(passport_data, secret)
    return hmac.compare_digest(recorded_hash, computed_hash) and hmac.compare_digest(
        recorded_sig, computed_sig
    )


def compute_bundle_hash(passport_hashes: List[str]) -> str:
    """Compute a single aggregate hash for multiple passports in an order."""
    sorted_hashes = sorted(passport_hashes)
    combined = ":".join(sorted_hashes).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()

