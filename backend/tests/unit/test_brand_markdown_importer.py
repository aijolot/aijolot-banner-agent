from __future__ import annotations

from pathlib import Path

import pytest

from app.services.brands.markdown_importer import BrandMarkdownImporter, BrandMarkdownImportError, dump_markdown


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


def test_importer_loads_color_system_from_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "color_roles.md"
    path.write_text(
        """---
id: color_roles
name: Color Roles
palette:
- name: Legacy Primary
  hex: '#111111'
color_system:
  primary:
    key: primary
    label: Hero Ink
    hex: '#111111'
    usage_hint: Use for hero headlines.
    agent_hint: Dominant brand anchor.
    variants:
    - name: Hero Ink Soft
      hex: '#222222'
      usage_hint: Use for muted anchors.
      source: seed
  secondary:
    key: secondary
    label: Warm Paper
    hex: '#F5E8D0'
    usage_hint: Use for backgrounds.
    agent_hint: Support the primary color.
  tertiary:
    key: tertiary
    label: Coral CTA
    hex: '#FF6655'
    usage_hint: Use for CTAs.
    agent_hint: Apply sparingly for attention.
shopify:
  store_domain: roles.myshopify.com
---

Color-role notes.
""",
        encoding="utf-8",
    )

    brand = BrandMarkdownImporter(base_dir=tmp_path).load_path(path)

    assert brand.color_system is not None
    assert brand.color_system.primary.label == "Hero Ink"
    assert brand.color_system.primary.variants[0].hex == "#222222"
    assert brand.color_system.tertiary.agent_hint == "Apply sparingly for attention."


def test_dump_markdown_writes_color_system_frontmatter(tmp_path: Path) -> None:
    source = tmp_path / "color_roles.md"
    source.write_text(
        """---
id: color_roles
name: Color Roles
palette:
- name: Legacy Primary
  hex: '#111111'
color_system:
  primary:
    key: primary
    label: Hero Ink
    hex: '#111111'
  secondary:
    key: secondary
    label: Warm Paper
    hex: '#F5E8D0'
  tertiary:
    key: tertiary
    label: Coral CTA
    hex: '#FF6655'
shopify:
  store_domain: roles.myshopify.com
---

Round trip notes.
""",
        encoding="utf-8",
    )
    brand = BrandMarkdownImporter(base_dir=tmp_path).load_path(source)
    output = tmp_path / "round_trip.md"

    output.write_text(dump_markdown(brand), encoding="utf-8")
    reloaded = BrandMarkdownImporter(base_dir=tmp_path).load_path(output)

    assert "color_system:" in output.read_text(encoding="utf-8")
    assert reloaded.color_system is not None
    assert reloaded.color_system.primary.label == "Hero Ink"
    assert reloaded.color_system.tertiary.hex == "#FF6655"


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
