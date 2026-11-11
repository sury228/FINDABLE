"""Database connection, engine configuration, and session management."""

import json
from pathlib import Path
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import get_settings
from app.models import Shop, Product, Shade, BuyerReference

settings = get_settings()

# SQLite engine configuration (check_same_thread=False for FastAPI async handlers)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)


def init_db() -> None:
    """Create all database tables and seed demo data if empty."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_db(session)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with Session(engine) as session:
        yield session


def seed_db(session: Session) -> None:
    """Seed Priya's demo shop, foundation product, 12 shades, and buyer references."""
    from app.passport import create_shade_passport_dict, sign_passport

    seed_file = Path("data/seed/seed_data.json")
    data: dict = {}
    if seed_file.exists():
        with open(seed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    # --- Always seed BuyerReferences (idempotent, runs every startup) ---
    for ref in data.get("buyer_references", []):
        existing = session.get(BuyerReference, ref["id"])
        if not existing:
            l_val = int(ref["L"] / 100 * 255)
            approx_hex = f"#{l_val:02X}{max(0,l_val-20):02X}{max(0,l_val-40):02X}"
            session.add(BuyerReference(
                ref_code=ref["id"],
                L=ref["L"],
                a=ref["a"],
                b=ref["b"],
                hex=approx_hex,
                confidence=ref.get("confidence", 92),
            ))
    session.commit()

    # --- Only seed shop / products / shades once ---
    existing_shop = session.exec(select(Shop)).first()
    if existing_shop:
        return

    shop_data = data.get("shop", {})
    products_data = data.get("products", [])

    if not shop_data:
        # Fallback minimal seed
        fallback_shop = Shop(
            id="shop_priya_beauty",
            name="Priya's Clean Beauty",
            payee_email="priya-seller@findable.demo",
        )
        session.add(fallback_shop)
        fallback_product = Product(
            id="prd_serum_foundation",
            shop_id=fallback_shop.id,
            name="Featherweight Serum Foundation",
            category="foundation",
            price_usd=28.00,
            finish="natural satin",
            coverage="medium buildable",
            description="Clean, breathable formulation calibrated across global undertones.",
            stock=100,
        )
        session.add(fallback_product)
        session.commit()
        return

    shop = Shop(
        id=shop_data.get("id", "shop_priya_beauty"),
        name=shop_data.get("name", "Priya's Clean Beauty"),
        payee_email=shop_data.get("payee_email", "priya-seller@findable.demo"),
    )
    session.add(shop)

    for p in products_data:
        product = Product(
            id=p["id"],
            shop_id=shop.id,
            name=p["name"],
            category=p.get("category", "foundation"),
            price_usd=p.get("price_usd", 28.00),
            finish=p.get("finish", "natural satin"),
            coverage=p.get("coverage", "medium buildable"),
            description=p.get("description", "Weightless serum foundation with skin-barrier hydration."),
            stock=p.get("stock", 150),
        )
        session.add(product)

        for s in p.get("shades", []):
            shade = Shade(
                id=s["id"],
                product_id=product.id,
                shade_name=s["shade_name"],
                hex=s["hex"],
                L=s["L"],
                a=s["a"],
                b=s["b"],
                chroma=s["chroma"],
                hue_deg=s["hue_deg"],
                ita_deg=s["ita_deg"],
                depth=s["depth"],
                undertone=s["undertone"],
                confidence=s.get("confidence", 92),
                source="seed",
            )
            session.add(shade)
            session.flush()  # get measured_at set

            # Recompute passport hash at seed time (not from seed_data.json)
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
                method_reference="seed data (not photographed)",
            )
            p_hash, p_sig = sign_passport(passport)
            shade.passport_hash = p_hash
            shade.passport_sig = p_sig
            session.add(shade)

    session.commit()
