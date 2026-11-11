"""Product listing generation using Vision LLM with offline fallback."""

from typing import Optional
from app.llm.client import LLMClient


async def generate_product_listing(
    product_name: str,
    category: str,
    finish: str,
    coverage: str,
    seller_notes: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
) -> str:
    """Generate professional marketing copy and product overview from metadata and photo."""
    client = LLMClient()

    prompt = (
        f"Draft a concise, appealing 2-sentence e-commerce description for a {category} product named '{product_name}'. "
        f"Key attributes: finish={finish}, coverage={coverage}. "
        f"Seller notes: {seller_notes or 'clean indie formulation, skin-mimicking pigment'}. "
        f"Emphasize precise shade measurement and natural finish."
    )

    system_prompt = (
        "You are an expert copywriter for premium clean indie cosmetic brands. "
        "Keep descriptions under 50 words, authentic, and modern."
    )

    return await client.generate_text(
        prompt=prompt,
        system_prompt=system_prompt,
        image_bytes=image_bytes,
    )

