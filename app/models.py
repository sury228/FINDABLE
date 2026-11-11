"""Database models and schemas for Findable."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


# ==============================================================================
# Database Tables (SQLModel)
# ==============================================================================

class Shop(SQLModel, table=True):
    """Beauty brand or indie seller shop."""
    id: str = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    payee_email: str = Field(description="PayPal sandbox business account email")
    created_at: datetime = Field(default_factory=utc_now)

    products: List["Product"] = Relationship(back_populates="shop")


class Product(SQLModel, table=True):
    """Product entity (e.g. foundation, concealer)."""
    id: str = Field(default=None, primary_key=True)
    shop_id: str = Field(foreign_key="shop.id", index=True)
    name: str
    category: str = Field(default="foundation", description="foundation, concealer, lipstick")
    price_usd: float = Field(default=0.0)
    finish: str = Field(default="natural", description="matte, dewy, satin, natural")
    coverage: str = Field(default="medium", description="sheer, medium, full")
    description: str = Field(default="")
    photo_path: Optional[str] = Field(default=None)
    stock: int = Field(default=100)

    shop: Optional[Shop] = Relationship(back_populates="products")
    shades: List["Shade"] = Relationship(back_populates="product")


class Shade(SQLModel, table=True):
    """Measured shade with physical CIELAB coordinates and cryptographic passport."""
    id: str = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id", index=True)
    shade_name: str
    hex: str
    L: float
    a: float
    b: float
    chroma: float
    hue_deg: float
    ita_deg: float
    depth: str = Field(description="very light, light, medium, tan, deep, rich")
    undertone: str = Field(description="warm, neutral, cool")
    confidence: int = Field(default=100, description="Measurement confidence 0-100")
    source: str = Field(default="seed", description="'seed' for seeded shades, 'measured' for photographed")
    swatch_photo_path: Optional[str] = Field(default=None)
    box: Optional[str] = Field(default=None, description="JSON coordinates [x0, y0, x1, y1]")
    measured_at: datetime = Field(default_factory=utc_now)
    passport_hash: Optional[str] = Field(default=None, description="SHA-256 canonical hash")
    passport_sig: Optional[str] = Field(default=None, description="HMAC-SHA256 signature")

    product: Optional[Product] = Relationship(back_populates="shades")


class BuyerReference(SQLModel, table=True):
    """Customer-measured reference shade (e.g. REF-7K2Q)."""
    ref_code: str = Field(primary_key=True, description="E.g., REF-7K2Q")
    L: float
    a: float
    b: float
    hex: str
    confidence: int = Field(default=100)
    created_at: datetime = Field(default_factory=utc_now)


class Order(SQLModel, table=True):
    """Commerce order record linking agent purchase to PayPal transaction."""
    id: str = Field(default=None, primary_key=True)
    paypal_order_id: Optional[str] = Field(default=None, index=True)
    invoice_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="CREATED", description="CREATED, APPROVED, COMPLETED, FAILED, REFUNDED")
    items_json: str = Field(description="Serialized JSON list of ordered items")
    total: float = Field(default=0.0)
    currency: str = Field(default="USD")
    channel: str = Field(default="agent", description="agent or web")
    agent_name: Optional[str] = Field(default="claude-desktop")
    passport_bundle_hash: Optional[str] = Field(default=None)
    capture_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class PayPalLog(SQLModel, table=True):
    """Persistent PayPal API request/response audit trail."""
    id: Optional[int] = Field(default=None, primary_key=True)
    method: str
    endpoint: str
    status: int
    debug_id: Optional[str] = Field(default=None)
    mode: str = Field(default="SANDBOX")
    created_at: datetime = Field(default_factory=utc_now)


class WebhookEvent(SQLModel, table=True):
    """Idempotency record for incoming PayPal webhook events."""
    paypal_event_id: str = Field(primary_key=True)
    event_type: str
    received_at: datetime = Field(default_factory=utc_now)
    processed: bool = Field(default=True)


# ==============================================================================
# Pydantic Schemas for DTOs & API Contracts
# ==============================================================================

class ColorBox(BaseModel):
    """Bounding box coordinates [x0, y0, x1, y1] on original image."""
    x0: int
    y0: int
    x1: int
    y1: int


class SwatchMeasurementRequest(BaseModel):
    """Payload to calibrate an image and measure designated swatch regions."""
    paper_box: ColorBox
    swatch_boxes: List[ColorBox]
    shade_names: Optional[List[str]] = None


class ShadePassport(BaseModel):
    """Verifiable, signed Shade Passport JSON schema."""
    passport_version: str = "1.0"
    shade_id: str
    product: dict
    shade_name: str
    measured: dict
    labels: dict
    confidence: int
    method: dict
    measured_at: str
    hash: Optional[str] = None
    signature: Optional[str] = None


class MatchResult(BaseModel):
    """Ranked shade match item for shopping agent."""
    shade_id: str
    product_id: str
    product_name: str
    shade_name: str
    hex: str
    price: float
    delta_e: float
    undertone_match: bool
    label: str = PydanticField(description="match, close, different")
    explanation: str


class CheckoutRequest(BaseModel):
    """Order checkout request initiated by an agent or human."""
    items: List[dict] = PydanticField(description="List of {shade_id: str, quantity: int}")
    agent_name: Optional[str] = "web-agent"
