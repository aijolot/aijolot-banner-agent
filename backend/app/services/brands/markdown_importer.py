from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.schemas.brand import BrandContext


DEFAULT_BRANDS_DIR = Path(__file__).resolve().parents[4] / "brands"
_FENCE = "---"


class BrandMarkdownImportError(ValueError):
    """Raised when a markdown seed cannot be safely imported."""


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    stripped = text.lstrip()
    if not stripped.startswith(_FENCE):
        return {}, text
    rest = stripped[len(_FENCE) :]
    end = rest.find("\n" + _FENCE)
    if end == -1:
        return {}, text
    raw = rest[:end]
    body = rest[end + len(_FENCE) + 1 :].lstrip("\n")
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        raise BrandMarkdownImportError("frontmatter must be a mapping")
    return loaded, body


class BrandMarkdownImporter:
    """Parse versioned brand markdown seeds into BrandContext models."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BRANDS_DIR

    def path_for_id(self, brand_id: str) -> Path:
        if not brand_id or "/" in brand_id or "\\" in brand_id or brand_id.startswith("."):
            raise BrandMarkdownImportError("invalid brand id")
        return self.base_dir / f"{brand_id}.md"

    def load_id(self, brand_id: str) -> BrandContext:
        return self.load_path(self.path_for_id(brand_id))

    def load_path(self, path: Path | str) -> BrandContext:
        source = Path(path)
        if not source.is_absolute():
            source = (self.base_dir / source).resolve()
        else:
            source = source.resolve()
        base = self.base_dir.resolve()
        try:
            source.relative_to(base)
        except ValueError as exc:
            raise BrandMarkdownImportError("brand markdown path is outside the configured brands directory") from exc
        if source.suffix != ".md":
            raise BrandMarkdownImportError("brand markdown path must end with .md")
        if not source.exists():
            raise FileNotFoundError(source)
        frontmatter, body = split_frontmatter(source.read_text(encoding="utf-8"))
        frontmatter.setdefault("id", source.stem)
        frontmatter["notes"] = body
        try:
            return BrandContext(**frontmatter)
        except ValidationError as exc:
            raise BrandMarkdownImportError(f"invalid brand markdown: {exc}") from exc

    def list_seed_brands(self) -> list[BrandContext]:
        if not self.base_dir.exists():
            return []
        return [self.load_path(path) for path in sorted(self.base_dir.glob("*.md"))]


def dump_markdown(brand: BrandContext) -> str:
    data = brand.model_dump(exclude={"notes"})
    frontmatter = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    body = brand.notes.rstrip()
    return f"{_FENCE}\n{frontmatter}\n{_FENCE}\n\n{body}\n"
