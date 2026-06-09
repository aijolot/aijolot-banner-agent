from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.state import BannerAssets, Concept, Variant

_HANDLE_RE = re.compile(r"[^a-z0-9_-]+")
_LIQUID_ESCAPE = {"\n": " ", "\r": " "}


@dataclass(frozen=True)
class LiquidPayload:
    section_filename: str
    snippet_filename: str
    config_filename: str
    section: str
    block_snippet: str
    config: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "section_filename": self.section_filename,
            "snippet_filename": self.snippet_filename,
            "config_filename": self.config_filename,
            "section": self.section,
            "block_snippet": self.block_snippet,
            "config": self.config,
        }


def _dump_model(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def _handle(value: str, fallback: str = "banner") -> str:
    text = _HANDLE_RE.sub("-", (value or "").lower()).strip("-")
    return text[:48] or fallback


def _escape_liquid_string(value: Any) -> str:
    text = str(value or "")
    for src, dst in _LIQUID_ESCAPE.items():
        text = text.replace(src, dst)
    text = html.escape(text, quote=True).replace("'", "&#39;")
    text = text.replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")
    text = text.replace("{%", "&#123;%").replace("%}", "%&#125;")
    return text[:500]


def _asset_url(assets: BannerAssets | None) -> str:
    if not assets:
        return ""
    for mapping in (assets.webp, assets.avif, assets.fallback_jpg):
        clean = {int(k): str(v) for k, v in (mapping or {}).items() if str(k).isdigit() and v}
        if clean:
            return clean[max(clean)]
    for record in assets.asset_records:
        url = record.get("public_url") or record.get("url")
        if url:
            return str(url)
    return ""


def _variant_config(concept: Concept, variant: Variant) -> dict[str, str]:
    override = variant.copy_override or {}
    copy = concept.copy or {}
    return {
        "tag": _handle(variant.customer_tag, "default"),
        "headline": str(override.get("headline") or copy.get("headline") or "Seasonal offer"),
        "subheadline": str(override.get("subheadline") or override.get("body") or copy.get("subheadline") or copy.get("body") or "Discover the collection."),
        "eyebrow": str(override.get("eyebrow") or copy.get("eyebrow") or "Featured"),
        "cta": str(override.get("cta") or copy.get("cta") or "Shop now"),
    }


def build_liquid_payload(
    concept: Concept,
    variants: list[Variant] | None = None,
    *,
    brand: Any = None,
    assets: BannerAssets | None = None,
    placement: str | dict[str, Any] | None = None,
    cta_url: str | None = None,
) -> LiquidPayload:
    """Build a controlled Shopify OS 2.0 section/snippet/config payload.

    No untrusted Liquid is accepted from inputs. User strings are pre-escaped once
    before being embedded as controlled snippet arguments; URL settings are still
    rendered through Liquid's escape filter at storefront time.
    """

    brand_data = _dump_model(brand)
    brand_name = str(brand_data.get("name") or getattr(brand, "name", "Aijolot") or "Aijolot")
    headline = str((concept.copy or {}).get("headline") or "banner")
    slug_seed = f"{brand_name}-{headline}"
    digest = hashlib.sha1(slug_seed.encode("utf-8")).hexdigest()[:8]
    slug = f"aijolot-{_handle(headline)}-{digest}"

    variant_rows = [_variant_config(concept, v) for v in (variants or [])]
    if not variant_rows:
        variant_rows = [_variant_config(concept, Variant(customer_tag="default", intent_delta="", copy_override=None))]
    if not any(v["tag"] == "default" for v in variant_rows):
        variant_rows.insert(0, {**variant_rows[0], "tag": "default"})

    image_url = _asset_url(assets)
    config = {
        "slug": slug,
        "brand_name": brand_name,
        "placement": placement or (brand_data.get("shopify") or {}).get("default_placement") or "hero",
        "palette_usage": dict(concept.palette_usage or {}),
        "image": {"url": image_url, "alt": getattr(assets, "alt_text_suggestion", "") if assets else ""},
        "variants": variant_rows,
        "audit": {"human_review_required": True, "auto_publish": False},
        "optimization_report": getattr(assets, "optimization_report", {}) if assets else {},
    }

    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    safe_image_url = _escape_liquid_string(image_url)
    # CTA destination from the brief (validated absolute URL or "/path"); the merchant
    # can still override it via the section setting. Default falls back to the catalog.
    cta_default = _escape_liquid_string(str(cta_url or "/collections/all"))
    snippet = """{% comment %} Aijolot controlled banner block. Do not inject raw Liquid from campaign inputs. {% endcomment %}
<div class=\"aijolot-banner__copy\">
  {% if eyebrow != blank %}<p class=\"aijolot-banner__eyebrow\">{{ eyebrow }}</p>{% endif %}
  <h2 class=\"aijolot-banner__headline\">{{ headline }}</h2>
  {% if subheadline != blank %}<p class=\"aijolot-banner__subheadline\">{{ subheadline }}</p>{% endif %}
  {% if cta != blank %}<a class=\"aijolot-banner__cta\" href=\"{{ cta_url | default: routes.root_url | escape }}\">{{ cta }}</a>{% endif %}
</div>
"""

    cases = []
    for row in variant_rows:
        cases.append(
            "{% when '" + _escape_liquid_string(row["tag"]) + "' %}\n"
            "  {% assign matched_tag = 'matched' %}\n"
            "  {% render 'aijolot-banner-block', "
            "eyebrow: '" + _escape_liquid_string(row["eyebrow"]) + "', "
            "headline: '" + _escape_liquid_string(row["headline"]) + "', "
            "subheadline: '" + _escape_liquid_string(row["subheadline"]) + "', "
            "cta: '" + _escape_liquid_string(row["cta"]) + "', "
            "cta_url: section.settings.cta_url %}"
        )
    default_row = variant_rows[0]
    section = f"""{{% comment %}}
Aijolot Banner Agent OS 2.0 section. Payload config hash: {digest}.
{{% endcomment %}}
{{% comment %}} Config JSON for app/metafield publishing: {_escape_liquid_string(config_json)} {{% endcomment %}}
<section class=\"aijolot-banner aijolot-banner--{slug}\" aria-label=\"{_escape_liquid_string(brand_name)} promotion\">
  <div class=\"aijolot-banner__media\" style=\"background-image:url('{{{{ section.settings.image_url | default: '{safe_image_url}' | escape }}}}')\"></div>
  {{% assign matched_tag = 'default' %}}
  {{% for tag in customer.tags %}}
    {{% assign normalized_tag = tag | handleize %}}
    {{% if matched_tag == 'default' %}}
      {{% case normalized_tag %}}
{chr(10).join(cases)}
      {{% endcase %}}
    {{% endif %}}
  {{% endfor %}}
  {{% if matched_tag == 'default' %}}
    {{% render 'aijolot-banner-block', eyebrow: '{_escape_liquid_string(default_row['eyebrow'])}', headline: '{_escape_liquid_string(default_row['headline'])}', subheadline: '{_escape_liquid_string(default_row['subheadline'])}', cta: '{_escape_liquid_string(default_row['cta'])}', cta_url: section.settings.cta_url %}}
  {{% endif %}}
</section>

{{% schema %}}
{{
  "name": "Aijolot campaign banner",
  "settings": [
    {{"type":"url","id":"image_url","label":"Background image URL"}},
    {{"type":"text","id":"cta_url","label":"CTA URL","default":"{cta_default}"}}
  ],
  "presets": [{{"name":"Aijolot campaign banner"}}]
}}
{{% endschema %}}
"""
    return LiquidPayload(
        section_filename=f"sections/{slug}.liquid",
        snippet_filename="snippets/aijolot-banner-block.liquid",
        config_filename=f"config/aijolot/{slug}.json",
        section=section,
        block_snippet=snippet,
        config=config,
    )


__all__ = ["LiquidPayload", "build_liquid_payload"]
