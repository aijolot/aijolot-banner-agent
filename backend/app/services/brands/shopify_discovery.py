"""Shopify theme/brand evidence collector (brand discovery, Task 3).

Pulls safe, capped brand evidence (colors, fonts, logo/banner/hero assets) from
the Shopify Admin API and emits a :class:`BrandDiscoverySnapshot`. The snapshot
is raw evidence with provenance; it is never auto-applied to the approved
``BrandContext``.

Safety rules:

- Only Shopify Admin API calls through the provided client; no arbitrary
  external URL fetches.
- Allowlisted theme asset keys with a per-asset byte cap; CSS files are picked
  from the asset index (at most ``max_css_assets``).
- Each source is guarded: one failing source appends a human-readable message
  to ``snapshot.errors`` and degrades the run to ``partial`` instead of
  raising. ``failed`` is reserved for runs where nothing could be fetched.
- Access tokens are never read, logged, or embedded in errors/snapshots.
- Extracted fonts are normalized through the same whitelist validators used by
  the brand schema, so CSS junk (``var(...)``, ``!important``, injection
  attempts) is parsed down to clean families or dropped.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.schemas.brand import _normalize_font_family, _normalize_font_stack
from app.schemas.brand_discovery import (
    BrandDiscoveryAsset,
    BrandDiscoverySnapshot,
    DiscoveredColor,
    DiscoveredFont,
)

DEFAULT_MAX_ASSET_BYTES = 256 * 1024
DEFAULT_MAX_CSS_ASSETS = 5
MAX_SECTION_ASSETS = 6

# Confidence heuristics by evidence source.
CONFIDENCE_SHOP_BRAND = 0.95
CONFIDENCE_THEME_SETTINGS = 0.9
CONFIDENCE_CSS_VARIABLE = 0.6
CONFIDENCE_CSS_FONT = 0.6
CONFIDENCE_SCHEMA_DEFAULT = 0.5
CONFIDENCE_CSS_RAW_HEX = 0.4

SETTINGS_ASSET_KEYS = ("config/settings_data.json", "config/settings_schema.json")
SECTION_ASSET_ALLOWLIST = (
    "sections/header.liquid",
    "sections/hero.liquid",
    "sections/image-banner.liquid",
    "sections/slideshow.liquid",
    "layout/theme.liquid",
)
_CSS_KEY_SUFFIXES = (".css", ".css.liquid", ".scss.liquid")
_CSS_KEY_HINTS = ("base", "theme", "main", "style", "global")

_AssetKind = Literal["logo", "banner", "hero", "theme_asset", "css", "settings", "unknown"]

_FULL_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
_HEX_IN_TEXT_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_CSS_COLOR_VAR_RE = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3}))\b")
# Lookbehind keeps ``--font-family-ish`` custom properties out of the plain
# declaration regex; the dedicated custom-property regex below handles those.
_CSS_FONT_FAMILY_RE = re.compile(r"(?<![\w-])font-family\s*:\s*([^;{}]+)", re.IGNORECASE)
_CSS_FONT_VAR_RE = re.compile(r"--([A-Za-z0-9_-]*font[A-Za-z0-9_-]*)\s*:\s*([^;{}]+)", re.IGNORECASE)
# Shopify font_picker values look like ``helvetica_n4`` / ``neue_haas_unica_i7``.
_FONT_PICKER_RE = re.compile(r"^([a-z0-9_]+)_[nib][0-9]$")
_NUMERIC_TOKEN_RE = re.compile(r"[\d.]+[a-z%]*", re.IGNORECASE)
_IMAGE_EXT_RE = re.compile(r"\.(?:png|jpe?g|webp|svg|gif)(?:\?|$)", re.IGNORECASE)
_HTTPS_IMAGE_URL_RE = re.compile(
    r"https://[^\s\"'<>()]+?\.(?:png|jpe?g|webp|svg|gif)(?:\?[^\s\"'<>()]*)?",
    re.IGNORECASE,
)
_LIQUID_ASSET_REF_RE = re.compile(
    r"[\"']([A-Za-z0-9_./-]+\.(?:png|jpe?g|webp|svg|gif))[\"']\s*\|\s*asset_url",
    re.IGNORECASE,
)

# CSS generic families may stay in a stack but never count as the primary family.
_GENERIC_FONT_FAMILIES = {
    "sans-serif",
    "serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
    "ui-rounded",
    "math",
    "emoji",
    "fangsong",
}
# CSS-wide keywords / weight-style tokens that are never font families.
_NON_FAMILY_TOKENS = {
    "bold",
    "bolder",
    "lighter",
    "normal",
    "italic",
    "oblique",
    "regular",
    "medium",
    "light",
    "semibold",
    "extrabold",
    "heavy",
    "thin",
    "small-caps",
    "inherit",
    "initial",
    "unset",
    "revert",
    "revert-layer",
    "none",
    "auto",
    "true",
    "false",
}


class ShopifyDiscoveryClient(Protocol):
    """Read-only subset of :class:`ShopifyAdminClient` used by discovery."""

    def get_shop_metadata(self, *, include_brand: bool = True) -> dict[str, Any]: ...
    def get_main_theme(self) -> dict[str, Any] | None: ...
    def list_theme_assets(self, *, theme_id: str) -> list[dict[str, Any]]: ...
    def get_theme_asset(self, *, theme_id: str, key: str) -> dict[str, Any] | None: ...


def collect_brand_evidence(
    client: ShopifyDiscoveryClient,
    *,
    brand_id: str,
    shop_domain: str,
    store_id: str | None = None,
    max_css_assets: int = DEFAULT_MAX_CSS_ASSETS,
    max_asset_bytes: int = DEFAULT_MAX_ASSET_BYTES,
) -> BrandDiscoverySnapshot:
    """Collect Shopify brand evidence into a :class:`BrandDiscoverySnapshot`.

    Never raises for HTTP/scope/parse failures: every source is independently
    guarded and failures are recorded in ``snapshot.errors`` (status becomes
    ``partial``, or ``failed`` when nothing at all could be fetched).
    """

    run = _CollectorRun(
        client,
        brand_id=brand_id,
        shop_domain=shop_domain,
        store_id=store_id,
        max_css_assets=max_css_assets,
        max_asset_bytes=max_asset_bytes,
    )
    return run.collect()


# ---------------------------------------------------------------------------
# Parsing helpers (pure functions)
# ---------------------------------------------------------------------------


def _expand_hex(value: str) -> str:
    """``#RGB`` -> ``#RRGGBB`` (already-long values pass through), uppercased."""

    body = value[1:]
    if len(body) == 3:
        body = "".join(ch * 2 for ch in body)
    return f"#{body.upper()}"


def _full_hex_or_none(value: str) -> str | None:
    return _expand_hex(value) if _FULL_HEX_RE.match(value) else None


def _parse_font_stack(raw: str) -> tuple[str, str] | None:
    """Parse a raw ``font-family`` value into ``(family, css_stack)``.

    Strips quotes/``!important``, drops ``var(...)`` references, numeric/keyword
    tokens, and anything that fails the brand schema whitelist. Returns ``None``
    when no safe non-generic family remains (generic-only stacks map to nothing).
    """

    value = re.sub(r"!\s*important", "", raw, flags=re.IGNORECASE)
    families: list[str] = []
    for part in value.split(","):
        part = part.strip()
        if len(part) >= 2 and part[0] == part[-1] and part[0] in "'\"":
            part = part[1:-1].strip()
        if not part or "(" in part or ")" in part:
            continue  # var()/url()/function references are never families
        if any(quote in part for quote in "'\""):
            continue  # unbalanced or embedded quotes -> unsafe fragment
        if _NUMERIC_TOKEN_RE.fullmatch(part) or part.lower() in _NON_FAMILY_TOKENS:
            continue
        try:
            family = _normalize_font_family(part)
        except ValueError:
            continue  # whitelist rejected it (injection/junk) -> drop token
        families.append(family)
    primary = next((f for f in families if f.lower() not in _GENERIC_FONT_FAMILIES), None)
    if primary is None:
        return None
    try:
        stack = _normalize_font_stack(", ".join(dict.fromkeys(families)))
    except ValueError:  # pragma: no cover - families are individually validated
        stack = primary
    return primary, stack


def _font_family_from_picker(value: str) -> str | None:
    """``helvetica_n4`` -> ``Helvetica``; ``neue_haas_unica_i7`` -> ``Neue Haas Unica``."""

    match = _FONT_PICKER_RE.match(value.strip().lower())
    if not match:
        return None
    words = [word for word in match.group(1).split("_") if word]
    if not words:
        return None
    return " ".join(word.capitalize() for word in words)


def _looks_like_image_ref(value: str) -> bool:
    return value.startswith("shopify://") or bool(_IMAGE_EXT_RE.search(value))


def _iter_setting_strings(
    node: Any, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], str, dict[str, Any] | None]]:
    """Yield ``(path, string_value, parent_dict)`` for every string in a JSON tree."""

    if isinstance(node, dict):
        for key, value in node.items():
            key_path = path + (str(key),)
            if isinstance(value, str):
                yield key_path, value, node
            elif isinstance(value, (dict, list)):
                yield from _iter_setting_strings(value, key_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            index_path = path + (str(index),)
            if isinstance(value, str):
                yield index_path, value, None
            elif isinstance(value, (dict, list)):
                yield from _iter_setting_strings(value, index_path)


def _select_css_keys(entries: list[dict[str, Any]], *, max_bytes: int, limit: int) -> list[str]:
    """Pick at most ``limit`` stylesheet keys, preferring base/theme/main files."""

    candidates: list[tuple[int, int, str]] = []
    for entry in entries:
        key = entry.get("key")
        if not isinstance(key, str) or not key.startswith("assets/"):
            continue
        if not key.lower().endswith(_CSS_KEY_SUFFIXES):
            continue
        size = entry.get("size")
        if isinstance(size, (int, float)) and size > max_bytes:
            continue  # oversized stylesheets are simply not selected
        priority = 0 if any(hint in key.lower() for hint in _CSS_KEY_HINTS) else 1
        candidates.append((priority, len(key), key))
    return [key for _, _, key in sorted(candidates)[:limit]]


def _select_section_keys(entries: list[dict[str, Any]] | None) -> list[str]:
    """Allowlisted section/layout keys plus ``sections/hero*.liquid`` globs."""

    if entries is None:
        # Asset listing unavailable: try the fixed allowlist (each fetch guarded).
        return list(SECTION_ASSET_ALLOWLIST)[:MAX_SECTION_ASSETS]
    available = {entry.get("key") for entry in entries if isinstance(entry.get("key"), str)}
    keys = [key for key in SECTION_ASSET_ALLOWLIST if key in available]
    keys += sorted(
        key
        for key in available
        if isinstance(key, str)
        and key.startswith("sections/hero")
        and key.endswith(".liquid")
        and key not in keys
    )
    return keys[:MAX_SECTION_ASSETS]


def _asset_kind_for(section_key: str, ref: str) -> _AssetKind:
    ref_l, key_l = ref.lower(), section_key.lower()
    if "logo" in ref_l:
        return "logo"
    if "hero" in key_l or "hero" in ref_l:
        return "hero"
    if "banner" in key_l or "banner" in ref_l or "slideshow" in key_l:
        return "banner"
    if "header" in key_l:
        return "logo"
    return "theme_asset"


def _dedupe_colors(colors: list[DiscoveredColor]) -> list[DiscoveredColor]:
    best: dict[str, DiscoveredColor] = {}
    order: list[str] = []
    for color in colors:
        current = best.get(color.hex)
        if current is None:
            best[color.hex] = color
            order.append(color.hex)
        elif color.confidence > current.confidence:
            if not color.name and current.name:
                color = color.model_copy(update={"name": current.name})
            best[color.hex] = color
        elif not current.name and color.name:
            best[color.hex] = current.model_copy(update={"name": color.name})
    return [best[hex_value] for hex_value in order]


def _dedupe_fonts(fonts: list[DiscoveredFont]) -> list[DiscoveredFont]:
    best: dict[str, DiscoveredFont] = {}
    order: list[str] = []
    for font in fonts:
        key = font.family.lower()
        current = best.get(key)
        if current is None:
            best[key] = font
            order.append(key)
            continue
        winner, loser = (font, current) if font.confidence > current.confidence else (current, font)
        if not winner.css_stack and loser.css_stack:
            winner = winner.model_copy(update={"css_stack": loser.css_stack})
        best[key] = winner
    return [best[key] for key in order]


def _dedupe_assets(assets: list[BrandDiscoveryAsset]) -> list[BrandDiscoveryAsset]:
    seen: set[str] = set()
    out: list[BrandDiscoveryAsset] = []
    for asset in assets:
        key = json.dumps(
            [asset.kind, asset.url or "", asset.theme_asset_key or "", asset.metadata],
            sort_keys=True,
            default=str,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(asset)
    return out


def _summarize(
    *,
    colors: list[DiscoveredColor],
    fonts: list[DiscoveredFont],
    assets: list[BrandDiscoveryAsset],
    theme_metadata: dict[str, Any],
    errors: list[str],
) -> str:
    def bucket_of(source: str) -> str:
        return source.split(":", 1)[0]

    buckets: dict[str, dict[str, int]] = {}

    def count(source: str, category: str) -> None:
        counts = buckets.setdefault(bucket_of(source), {"colors": 0, "fonts": 0, "assets": 0})
        counts[category] += 1

    for color in colors:
        count(color.source, "colors")
    for font in fonts:
        count(font.source, "fonts")
    for asset in assets:
        count(asset.source, "assets")

    parts: list[str] = []
    if theme_metadata.get("theme_name"):
        parts.append(f"theme: {theme_metadata['theme_name']} (id {theme_metadata.get('theme_id', '?')})")
    known_order = ("shop_metadata", "theme_settings", "css", "section")
    ordered = [name for name in known_order if name in buckets]
    ordered += sorted(name for name in buckets if name not in known_order)
    for name in ordered:
        counts = buckets[name]
        fragments = [f"{value} {label}" for label, value in counts.items() if value]
        if fragments:
            parts.append(f"{name}: {', '.join(fragments)}")
    if errors:
        parts.append(f"errors: {len(errors)}")
    return "; ".join(parts) if parts else "no evidence collected"


# ---------------------------------------------------------------------------
# Collector run (single use, holds in-flight evidence)
# ---------------------------------------------------------------------------


class _CollectorRun:
    def __init__(
        self,
        client: ShopifyDiscoveryClient,
        *,
        brand_id: str,
        shop_domain: str,
        store_id: str | None,
        max_css_assets: int,
        max_asset_bytes: int,
    ) -> None:
        self.client = client
        self.brand_id = brand_id
        self.shop_domain = shop_domain
        self.store_id = store_id
        self.max_css_assets = max_css_assets
        self.max_asset_bytes = max_asset_bytes
        self.colors: list[DiscoveredColor] = []
        self.fonts: list[DiscoveredFont] = []
        self.assets: list[BrandDiscoveryAsset] = []
        self.theme_metadata: dict[str, Any] = {}
        self.errors: list[str] = []

    # -- evidence sinks (schema-validated; invalid items are dropped) -------

    def _add_color(
        self, *, hex_value: str, name: str, source: str, confidence: float, usage_hint: str = ""
    ) -> None:
        try:
            self.colors.append(
                DiscoveredColor(
                    hex=hex_value, name=name, source=source, confidence=confidence, usage_hint=usage_hint
                )
            )
        except ValidationError:
            pass

    def _add_font(
        self, *, family: str, css_stack: str, source: str, confidence: float, sample_usage: str = ""
    ) -> None:
        try:
            self.fonts.append(
                DiscoveredFont(
                    family=family,
                    css_stack=css_stack,
                    source=source,
                    confidence=confidence,
                    sample_usage=sample_usage,
                )
            )
        except ValidationError:
            pass

    def _add_asset(
        self,
        *,
        kind: _AssetKind,
        source: str,
        url: str | None = None,
        theme_asset_key: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.assets.append(
                BrandDiscoveryAsset(
                    kind=kind,
                    url=url,
                    theme_asset_key=theme_asset_key,
                    content_type=content_type,
                    source=source,
                    metadata=metadata or {},
                )
            )
        except ValidationError:
            pass

    # -- top-level flow ------------------------------------------------------

    def collect(self) -> BrandDiscoverySnapshot:
        self._collect_shop_metadata()
        theme_id = self._collect_theme_metadata()
        if theme_id:
            entries = self._list_theme_assets(theme_id)
            self._collect_settings_assets(theme_id)
            self._collect_css_assets(theme_id, entries)
            self._collect_section_assets(theme_id, entries)
        return self._build_snapshot()

    def _build_snapshot(self) -> BrandDiscoverySnapshot:
        colors = _dedupe_colors(self.colors)
        fonts = _dedupe_fonts(self.fonts)
        assets = _dedupe_assets(self.assets)
        has_evidence = bool(colors or fonts or assets or self.theme_metadata)
        if not self.errors:
            status = "succeeded"
        elif has_evidence:
            status = "partial"
        else:
            status = "failed"
        return BrandDiscoverySnapshot(
            id=f"disc_{uuid4().hex[:12]}",
            brand_id=self.brand_id,
            store_id=self.store_id,
            shop_domain=self.shop_domain,
            status=status,
            discovered_at=datetime.now(timezone.utc),
            source_summary=_summarize(
                colors=colors,
                fonts=fonts,
                assets=assets,
                theme_metadata=self.theme_metadata,
                errors=self.errors,
            ),
            assets=assets,
            colors=colors,
            fonts=fonts,
            theme_metadata=dict(self.theme_metadata),
            errors=list(self.errors),
        )

    # -- source 1: shop metadata --------------------------------------------

    def _collect_shop_metadata(self) -> None:
        shop: dict[str, Any] | None = None
        try:
            shop = self.client.get_shop_metadata(include_brand=True)
        except Exception as exc:
            self.errors.append(f"shop_metadata: brand metadata unavailable ({exc})")
            try:
                shop = self.client.get_shop_metadata(include_brand=False)
            except Exception as basic_exc:
                self.errors.append(f"shop_metadata: shop query failed ({basic_exc})")
                return
        if not shop:
            self.errors.append("shop_metadata: empty shop payload")
            return
        try:
            self._extract_shop_metadata(shop)
        except Exception as exc:
            self.errors.append(f"shop_metadata: extraction failed ({exc})")

    def _extract_shop_metadata(self, shop: dict[str, Any]) -> None:
        source = "shop_metadata"
        name = shop.get("name")
        if isinstance(name, str) and name.strip():
            self.theme_metadata["shop_name"] = name.strip()
        primary_domain = shop.get("primaryDomain")
        if isinstance(primary_domain, dict):
            for field, meta_key in (("url", "shop_primary_domain_url"), ("host", "shop_primary_domain_host")):
                value = primary_domain.get(field)
                if isinstance(value, str) and value.strip():
                    self.theme_metadata[meta_key] = value.strip()
        brand = shop.get("brand")
        if not isinstance(brand, dict):
            return
        for text_field, meta_key in (("slogan", "brand_slogan"), ("shortDescription", "brand_short_description")):
            value = brand.get(text_field)
            if isinstance(value, str) and value.strip():
                self.theme_metadata[meta_key] = value.strip()
        brand_colors = brand.get("colors")
        if isinstance(brand_colors, dict):
            for group_name in ("primary", "secondary"):
                groups = brand_colors.get(group_name)
                if isinstance(groups, dict):
                    groups = [groups]
                if not isinstance(groups, list):
                    continue
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    for field in ("background", "foreground"):
                        value = group.get(field)
                        hex_value = _full_hex_or_none(value.strip()) if isinstance(value, str) else None
                        if hex_value:
                            self._add_color(
                                hex_value=hex_value,
                                name=f"brand {group_name} {field}",
                                source=source,
                                confidence=CONFIDENCE_SHOP_BRAND,
                                usage_hint=f"shop brand {group_name} color",
                            )
        for image_field, kind in (("logo", "logo"), ("squareLogo", "logo"), ("coverImage", "hero")):
            node = brand.get(image_field)
            image = node.get("image") if isinstance(node, dict) else None
            url = image.get("url") if isinstance(image, dict) else None
            if isinstance(url, str) and url.startswith("https://"):
                self._add_asset(kind=kind, url=url, source=source, metadata={"brand_field": image_field})

    # -- source 2: active theme ----------------------------------------------

    def _collect_theme_metadata(self) -> str | None:
        try:
            theme = self.client.get_main_theme()
        except Exception as exc:
            self.errors.append(f"theme: main theme lookup failed ({exc})")
            return None
        if not theme:
            self.errors.append("theme: no main (published) theme found")
            return None
        if theme.get("name"):
            self.theme_metadata["theme_name"] = str(theme["name"])
        if theme.get("role"):
            self.theme_metadata["theme_role"] = str(theme["role"])
        theme_id = str(theme.get("id") or "").strip()
        if not theme_id:
            self.errors.append("theme: main theme has no id; skipping theme assets")
            return None
        self.theme_metadata["theme_id"] = theme_id
        return theme_id

    def _list_theme_assets(self, theme_id: str) -> list[dict[str, Any]] | None:
        try:
            entries = self.client.list_theme_assets(theme_id=theme_id)
        except Exception as exc:
            self.errors.append(f"theme_assets: asset listing failed ({exc})")
            return None
        return [entry for entry in entries if isinstance(entry, dict)]

    def _fetch_text_asset(self, theme_id: str, key: str, label: str) -> tuple[str, str | None] | None:
        """Fetch a theme asset's text under the byte cap; failures append an error."""

        try:
            asset = self.client.get_theme_asset(theme_id=theme_id, key=key)
        except Exception as exc:
            self.errors.append(f"{label}: fetch failed ({exc})")
            return None
        if not asset:
            self.errors.append(f"{label}: asset not found")
            return None
        value = asset.get("value")
        if not isinstance(value, str) or not value:
            self.errors.append(f"{label}: no inline text value (binary or empty asset)")
            return None
        if len(value.encode("utf-8", errors="ignore")) > self.max_asset_bytes:
            self.errors.append(f"{label}: skipped, asset exceeds byte cap of {self.max_asset_bytes} bytes")
            return None
        return value, asset.get("content_type")

    # -- source 3: theme settings (config/*.json) -----------------------------

    def _collect_settings_assets(self, theme_id: str) -> None:
        for key in SETTINGS_ASSET_KEYS:
            label = f"theme_settings:{key}"
            fetched = self._fetch_text_asset(theme_id, key, label)
            if fetched is None:
                continue
            text, content_type = fetched
            self._add_asset(
                kind="settings",
                theme_asset_key=key,
                content_type=content_type,
                source=label,
                metadata={"bytes": len(text.encode("utf-8", errors="ignore"))},
            )
            try:
                self._extract_from_settings(key, text)
            except Exception as exc:
                self.errors.append(f"{label}: parse failed ({exc})")

    def _extract_from_settings(self, key: str, text: str) -> None:
        source = f"theme_settings:{key}"
        confidence = (
            CONFIDENCE_THEME_SETTINGS if key.endswith("settings_data.json") else CONFIDENCE_SCHEMA_DEFAULT
        )
        data = json.loads(text)
        for path, raw_value, parent in _iter_setting_strings(data):
            value = raw_value.strip()
            if not value:
                continue
            dotted = ".".join(path)
            setting_name = path[-1]
            # settings_schema entries keep the meaningful name in the sibling "id".
            if setting_name.lower() in {"default", "value"} and isinstance(parent, dict):
                parent_id = parent.get("id")
                if isinstance(parent_id, str) and parent_id:
                    setting_name = parent_id
            name_l = setting_name.lower()
            dotted_l = dotted.lower()

            hex_value = _full_hex_or_none(value)
            if hex_value:
                self._add_color(
                    hex_value=hex_value,
                    name=setting_name,
                    source=source,
                    confidence=confidence,
                    usage_hint=f"theme setting {dotted}",
                )
                continue
            if "font" in name_l:
                family = _font_family_from_picker(value)
                if family:
                    self._add_font(
                        family=family,
                        css_stack="",
                        source=source,
                        confidence=confidence,
                        sample_usage=f"theme setting {dotted}",
                    )
                    continue
                parsed = _parse_font_stack(value)
                if parsed:
                    self._add_font(
                        family=parsed[0],
                        css_stack=parsed[1],
                        source=source,
                        confidence=confidence,
                        sample_usage=f"theme setting {dotted}",
                    )
                continue
            if "logo" in name_l and _looks_like_image_ref(value):
                self._add_image_setting_asset(kind="logo", value=value, source=source, dotted=dotted)
                continue
            if name_l == "type" and any(token in value.lower() for token in ("hero", "banner", "slideshow")):
                kind: _AssetKind = "hero" if "hero" in value.lower() else "banner"
                self._add_asset(kind=kind, source=source, metadata={"section": dotted, "section_type": value})
                continue
            if _looks_like_image_ref(value) and any(
                token in name_l for token in ("image", "banner", "hero", "background")
            ):
                if "hero" in dotted_l:
                    kind = "hero"
                elif "banner" in dotted_l or "slideshow" in dotted_l:
                    kind = "banner"
                else:
                    kind = "theme_asset"
                self._add_image_setting_asset(kind=kind, value=value, source=source, dotted=dotted)

    def _add_image_setting_asset(self, *, kind: _AssetKind, value: str, source: str, dotted: str) -> None:
        url = value if value.startswith("https://") else None
        metadata: dict[str, Any] = {"setting": dotted}
        if url is None:
            metadata["raw_ref"] = value  # e.g. shopify://shop_images/... (not fetched)
        self._add_asset(kind=kind, url=url, source=source, metadata=metadata)

    # -- source 4: css assets --------------------------------------------------

    def _collect_css_assets(self, theme_id: str, entries: list[dict[str, Any]] | None) -> None:
        if entries is None:
            return  # listing failure already recorded; css keys are theme-specific
        for key in _select_css_keys(entries, max_bytes=self.max_asset_bytes, limit=self.max_css_assets):
            label = f"css:{key}"
            fetched = self._fetch_text_asset(theme_id, key, label)
            if fetched is None:
                continue
            text, content_type = fetched
            self._add_asset(
                kind="css",
                theme_asset_key=key,
                content_type=content_type,
                source=label,
                metadata={"bytes": len(text.encode("utf-8", errors="ignore"))},
            )
            try:
                self._extract_from_css(key, text)
            except Exception as exc:
                self.errors.append(f"{label}: parse failed ({exc})")

    def _extract_from_css(self, key: str, text: str) -> None:
        source = f"css:{key}"
        for match in _CSS_COLOR_VAR_RE.finditer(text):
            prop, raw_hex = match.groups()
            self._add_color(
                hex_value=_expand_hex(raw_hex),
                name=prop,
                source=source,
                confidence=CONFIDENCE_CSS_VARIABLE,
                usage_hint=f"css custom property --{prop}",
            )
        for match in _HEX_IN_TEXT_RE.finditer(text):
            self._add_color(
                hex_value=_expand_hex(match.group(0)),
                name="",
                source=source,
                confidence=CONFIDENCE_CSS_RAW_HEX,
                usage_hint="raw css color",
            )
        for match in _CSS_FONT_FAMILY_RE.finditer(text):
            parsed = _parse_font_stack(match.group(1))
            if parsed:
                self._add_font(
                    family=parsed[0],
                    css_stack=parsed[1],
                    source=source,
                    confidence=CONFIDENCE_CSS_FONT,
                    sample_usage="font-family declaration",
                )
        for match in _CSS_FONT_VAR_RE.finditer(text):
            prop, value = match.groups()
            parsed = _parse_font_stack(value)
            if parsed:
                self._add_font(
                    family=parsed[0],
                    css_stack=parsed[1],
                    source=source,
                    confidence=CONFIDENCE_CSS_VARIABLE,
                    sample_usage=f"--{prop}",
                )

    # -- source 5: section/layout files ----------------------------------------

    def _collect_section_assets(self, theme_id: str, entries: list[dict[str, Any]] | None) -> None:
        for key in _select_section_keys(entries):
            label = f"section:{key}"
            fetched = self._fetch_text_asset(theme_id, key, label)
            if fetched is None:
                continue
            text, _content_type = fetched
            try:
                self._extract_from_section(key, text)
            except Exception as exc:
                self.errors.append(f"{label}: parse failed ({exc})")

    def _extract_from_section(self, key: str, text: str) -> None:
        source = f"section:{key}"
        for match in _HTTPS_IMAGE_URL_RE.finditer(text):
            url = match.group(0)
            self._add_asset(kind=_asset_kind_for(key, url), url=url, source=source)
        for match in _LIQUID_ASSET_REF_RE.finditer(text):
            name = match.group(1)
            self._add_asset(
                kind=_asset_kind_for(key, name),
                theme_asset_key=f"assets/{name.lstrip('/')}",
                source=source,
                metadata={"liquid_filter": "asset_url"},
            )
