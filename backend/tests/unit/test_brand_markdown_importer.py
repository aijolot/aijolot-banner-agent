from __future__ import annotations

from pathlib import Path

import pytest

from app.services.brands.markdown_importer import BrandMarkdownImporter, BrandMarkdownImportError


def test_importer_parses_frontmatter_and_notes(tmp_path: Path) -> None:
    path = tmp_path / "test_brand.md"
    path.write_text(
        """---
id: test_brand
name: Test Brand
palette:
- name: Black
  hex: '#000000'
typography:
  display: Inter
  body: Arial
voice:
  tone:
  - Direct
  prohibited_words:
  - spam
  required_phrases:
  - hello
logo_url: https://example.com/logo.svg
image_style_directives:
- Clean studio lighting
shopify:
  store_domain: test.myshopify.com
  default_placement: hero
---

# Brand notes

Use concise copy.
""",
        encoding="utf-8",
    )

    brand = BrandMarkdownImporter(base_dir=tmp_path).load_path(path)

    assert brand.id == "test_brand"
    assert brand.name == "Test Brand"
    assert brand.palette[0].hex == "#000000"
    assert brand.voice.tone == ["Direct"]
    assert "Use concise copy" in brand.notes


def test_importer_uses_filename_as_id_when_frontmatter_omits_id(tmp_path: Path) -> None:
    path = tmp_path / "maison-hugo-boss-demo.md"
    path.write_text(
        """---
name: Filename Brand
palette:
- name: White
  hex: '#ffffff'
shopify:
  store_domain: filename.myshopify.com
---

Notes.
""",
        encoding="utf-8",
    )

    brand = BrandMarkdownImporter(base_dir=tmp_path).load_path(path)

    assert brand.id == "maison-hugo-boss-demo"
    assert brand.palette[0].hex == "#FFFFFF"


def test_path_for_id_allows_safe_hyphenated_slugs(tmp_path: Path) -> None:
    assert BrandMarkdownImporter(base_dir=tmp_path).path_for_id("maison-hugo-boss-demo") == tmp_path / "maison-hugo-boss-demo.md"


def test_importer_rejects_paths_outside_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "brands"
    base.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("---\nname: X\npalette: []\nshopify:\n  store_domain: x\n---\n", encoding="utf-8")

    importer = BrandMarkdownImporter(base_dir=base)

    with pytest.raises(BrandMarkdownImportError):
        importer.load_path(outside)
