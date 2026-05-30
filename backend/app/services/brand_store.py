"""Brand storage — read/write ``brands/{id}.md`` files.

Each brand lives in a markdown file with a YAML frontmatter block holding the
structured :class:`BrandContext` fields, followed by a free-form notes body::

    ---
    id: avocado_store
    name: Avocado Store
    ...
    ---

    # Notes...

This keeps brands diff-friendly and editable by hand, while the FastAPI bridge
serves them as validated JSON.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.schemas.brand import BrandContext, BrandSummary

# repo-root/brands  (this file is backend/app/services/brand_store.py)
BRANDS_DIR = Path(__file__).resolve().parents[3] / "brands"

_FENCE = "---"


class BrandNotFound(Exception):
    """Raised when a brand id has no backing ``.md`` file."""


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return ``(frontmatter_dict, body)`` from a markdown file's text."""
    stripped = text.lstrip()
    if not stripped.startswith(_FENCE):
        return {}, text
    # drop everything up to the first fence, then split on the closing fence
    rest = stripped[len(_FENCE):]
    end = rest.find("\n" + _FENCE)
    if end == -1:
        return {}, text
    fm_raw = rest[:end]
    body = rest[end + len(_FENCE) + 1:]
    data = yaml.safe_load(fm_raw) or {}
    return data, body.lstrip("\n")


def _dump_markdown(brand: BrandContext) -> str:
    """Serialize a BrandContext back into frontmatter + body."""
    data = brand.model_dump(exclude={"notes"})
    fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    body = brand.notes.rstrip()
    return f"{_FENCE}\n{fm}\n{_FENCE}\n\n{body}\n"


def _path(brand_id: str) -> Path:
    return BRANDS_DIR / f"{brand_id}.md"


def _load_file(path: Path) -> BrandContext:
    fm, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    fm["notes"] = body
    # ensure id matches filename even if frontmatter omits it
    fm.setdefault("id", path.stem)
    return BrandContext(**fm)


def list_brands() -> list[BrandSummary]:
    if not BRANDS_DIR.exists():
        return []
    out: list[BrandSummary] = []
    for path in sorted(BRANDS_DIR.glob("*.md")):
        brand = _load_file(path)
        out.append(BrandSummary(id=brand.id, name=brand.name, palette=brand.palette))
    return out


def get_brand(brand_id: str) -> BrandContext:
    path = _path(brand_id)
    if not path.exists():
        raise BrandNotFound(brand_id)
    return _load_file(path)


def save_brand(brand_id: str, brand: BrandContext) -> BrandContext:
    # the path is authoritative for the id
    brand = brand.model_copy(update={"id": brand_id})
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    _path(brand_id).write_text(_dump_markdown(brand), encoding="utf-8")
    return brand
