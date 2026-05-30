"""Brand endpoints (GH-26 / GH-17).

    GET  /brands           -> list of brand summaries
    GET  /brands/{id}      -> full BrandContext
    PUT  /brands/{id}      -> validate + persist, returns the saved BrandContext
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.brand import BrandContext, BrandSummary
from app.services import brand_store

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("", response_model=list[BrandSummary])
def list_brands() -> list[BrandSummary]:
    return brand_store.list_brands()


@router.get("/{brand_id}", response_model=BrandContext)
def get_brand(brand_id: str) -> BrandContext:
    try:
        return brand_store.get_brand(brand_id)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")


@router.put("/{brand_id}", response_model=BrandContext)
def put_brand(brand_id: str, brand: BrandContext) -> BrandContext:
    # Pydantic already validated the body (hex colors, arrays, etc.).
    return brand_store.save_brand(brand_id, brand)
