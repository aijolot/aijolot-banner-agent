"""ADK Tool: brand filesystem read/write.

Wraps app.services.brand_store. Reads brands/<brand_id>.md (YAML frontmatter
+ markdown body) into BrandContext; writes BrandContext back atomically.
"""

from __future__ import annotations

from app.schemas.brand import BrandContext
from app.services import brand_store


def read(brand_id: str) -> BrandContext:
    return brand_store.get_brand(brand_id)


def write(brand: BrandContext) -> None:
    brand_store.save_brand(brand.id, brand)
