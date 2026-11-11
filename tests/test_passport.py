"""Unit tests for cryptographic Shade Passport generation, canonical hashing, and HMAC signing."""

from app.passport import (
    canonical_json,
    compute_bundle_hash,
    create_shade_passport_dict,
    sign_passport,
    verify_passport,
)


def test_canonical_json_sorting():
    """Verify that canonical JSON sorts dictionary keys alphabetically regardless of input order."""
    d1 = {"b": 2, "a": 1, "c": {"y": 20, "x": 10}}
    d2 = {"a": 1, "c": {"x": 10, "y": 20}, "b": 2}
    assert canonical_json(d1) == canonical_json(d2)
    assert canonical_json(d1) == '{"a":1,"b":2,"c":{"x":10,"y":20}}'


def test_passport_signing_and_verification():
    """Verify that a signed Shade Passport verifies successfully and detects tampering."""
    secret = "test-secret-key-for-unit-tests"
    passport = create_shade_passport_dict(
        shade_id="shd_test01",
        product_id="prd_test",
        product_name="Test Foundation",
        category="foundation",
        price_usd=28.00,
        shade_name="Test Shade 01",
        hex_color="#C08C6C",
        lab=[62.4, 13.9, 24.1],
        chroma=27.8,
        hue_deg=60.0,
        ita_deg=27.2,
        depth="tan",
        undertone="neutral",
        confidence=95,
        measured_at="2026-11-10T12:00:00Z",
    )

    h, sig = sign_passport(passport, secret=secret)
    passport["hash"] = h
    passport["signature"] = sig

    # Valid passport verification
    assert verify_passport(passport, secret=secret) is True

    # Tampered data verification must fail
    tampered = dict(passport)
    tampered["confidence"] = 50
    assert verify_passport(tampered, secret=secret) is False


def test_compute_bundle_hash():
    """Verify bundle hash determinism regardless of input list ordering."""
    hashes = ["sha256:bbbb", "sha256:aaaa", "sha256:cccc"]
    h1 = compute_bundle_hash(hashes)
    h2 = compute_bundle_hash(list(reversed(hashes)))
    assert h1 == h2
    assert len(h1) == 64

