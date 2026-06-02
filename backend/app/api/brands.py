"""Brand endpoints (GH-26 / GH-17).

    GET  /brands           -> list of brand summaries
    GET  /brands/{id}      -> full BrandContext
    PUT  /brands/{id}      -> validate + persist, returns the saved BrandContext
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, ValidationError

from app.schemas.brand import BrandContext, BrandSummary
from app.services import brand_store
from app.services.brands.markdown_importer import BrandMarkdownImportError

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandImportRequest(BaseModel):
    brand_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")
    path: str | None = None


@router.get("", response_model=list[BrandSummary])
def list_brands() -> list[BrandSummary]:
    return brand_store.list_brands()


@router.post("/import", response_model=BrandContext)
def import_brand(request: BrandImportRequest) -> BrandContext:
    try:
        return brand_store.import_markdown_brand(brand_id=request.brand_id, path=request.path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="brand markdown file not found")
    except (BrandMarkdownImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


BrandIdPath = Annotated[str, Path(pattern=r"^[a-z0-9_-]+$")]


@router.get("/{brand_id}", response_model=BrandContext)
def get_brand(brand_id: BrandIdPath) -> BrandContext:
    try:
        return brand_store.get_brand(brand_id)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")


@router.put("/{brand_id}", response_model=BrandContext)
def put_brand(brand_id: BrandIdPath, brand: BrandContext) -> BrandContext:
    # Pydantic already validated the body (hex colors, arrays, etc.).
    try:
        return brand_store.save_brand(brand_id, brand)
    except (BrandMarkdownImportError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
