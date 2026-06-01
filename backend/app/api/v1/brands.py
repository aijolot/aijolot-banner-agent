from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field, ValidationError

from app.core.auth import require_user_context
from app.schemas.brand import BrandContext, BrandSummary
from app.services import brand_store
from app.services.brands.markdown_importer import BrandMarkdownImportError

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandImportRequest(BaseModel):
    brand_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")
    path: str | None = None


def _service(request: Request):
    context = require_user_context(request)
    return brand_store.service_for_team(context.team_id)


@router.get("", response_model=list[BrandSummary])
def list_brands(request: Request) -> list[BrandSummary]:
    return _service(request).list_brands()


@router.post("/import", response_model=BrandContext)
def import_brand(request: Request, payload: BrandImportRequest) -> BrandContext:
    try:
        return _service(request).import_markdown(brand_id=payload.brand_id, path=payload.path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="brand markdown file not found")
    except (BrandMarkdownImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


BrandIdPath = Annotated[str, Path(pattern=r"^[a-z0-9_-]+$")]


@router.get("/{brand_id}", response_model=BrandContext)
def get_brand(request: Request, brand_id: BrandIdPath) -> BrandContext:
    try:
        return _service(request).get_brand(brand_id)
    except brand_store.BrandNotFound:
        raise HTTPException(status_code=404, detail=f"brand '{brand_id}' not found")


@router.put("/{brand_id}", response_model=BrandContext)
def put_brand(request: Request, brand_id: BrandIdPath, brand: BrandContext) -> BrandContext:
    try:
        return _service(request).save_brand(brand_id, brand)
    except (BrandMarkdownImportError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
