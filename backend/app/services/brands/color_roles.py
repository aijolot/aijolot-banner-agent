from __future__ import annotations

import re
from typing import Any

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_ROLE_KEYS = ("primary", "secondary", "tertiary")

_USAGE_KEYWORDS = {
    "background": ("background", "surface", "field", "support"),
    "text": ("text", "copy", "headline", "type", "typography", "foreground"),
    "cta": ("cta", "button", "accent", "highlight", "badge", "urgency", "action"),
}

# Default usage group per role when the placement text gives no signal.
_ROLE_USAGE_GROUP = {"primary": "text", "secondary": "background", "tertiary": "cta"}


def dump_model(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def color_system_data(brand: Any) -> dict[str, Any]:
    data = dump_model(brand)
    color_system = data.get("color_system") or getattr(brand, "color_system", None)
    return dump_model(color_system)


def palette_lookup(brand: Any) -> dict[str, str]:
    data = dump_model(brand)
    palette = data.get("palette") or getattr(brand, "palette", []) or []
    out: dict[str, str] = {}
    for color in palette:
        item = dump_model(color)
        name = str(item.get("name") or "").strip()
        hex_value = str(item.get("hex") or "").strip()
        if name and _HEX_RE.match(hex_value):
            out[name] = hex_value.upper()
    return out


def role_data(brand: Any, role_key: str) -> dict[str, Any]:
    role = color_system_data(brand).get(role_key)
    return dump_model(role)


def choose_role_color(brand: Any, role_key: str, placement: str = "") -> dict[str, str]:
    """Choose an approved base role color or accepted variant for a placement.

    Variants are only selected from color_system.<role>.variants. When variants are
    absent, the role base color is returned. The returned token is intentionally a
    stable name/label/key so legacy Concept.palette_usage remains dict[str, str].
    """

    role = role_data(brand, role_key)
    if not role:
        palette = list(palette_lookup(brand).items())
        fallback_index = {"primary": 0, "secondary": 1, "tertiary": 2}.get(role_key, 0)
        if not palette:
            return {"token": role_key, "hex": "", "label": role_key.title(), "role": role_key, "source": "fallback"}
        name, hex_value = palette[min(fallback_index, len(palette) - 1)]
        return {"token": name, "hex": hex_value, "label": name, "role": role_key, "source": "palette"}

    placement_text = str(placement or "").lower()
    variants = [dump_model(v) for v in (role.get("variants") or [])]
    keyword_groups = []
    for group, keywords in _USAGE_KEYWORDS.items():
        if group in placement_text or any(word in placement_text for word in keywords):
            keyword_groups.extend(keywords)
    if not keyword_groups:
        keyword_groups = list(_USAGE_KEYWORDS.get(_ROLE_USAGE_GROUP.get(role_key, ""), ()))

    for variant in variants:
        hint = f"{variant.get('name', '')} {variant.get('usage_hint', '')}".lower()
        if any(keyword in hint for keyword in keyword_groups):
            name = str(variant.get("name") or role.get("label") or role_key).strip()
            hex_value = str(variant.get("hex") or "").strip().upper()
            if name and _HEX_RE.match(hex_value):
                return {"token": name, "hex": hex_value, "label": name, "role": role_key, "source": "variant"}

    label = str(role.get("label") or role.get("key") or role_key).strip()
    hex_value = str(role.get("hex") or "").strip().upper()
    return {"token": label or role_key, "hex": hex_value, "label": label or role_key, "role": role_key, "source": "base"}


def resolve_color_token(brand: Any, token: str) -> str:
    token = str(token or "").strip()
    if _HEX_RE.match(token):
        return token.upper()

    lowered = token.lower()
    color_system = color_system_data(brand)
    for role_key in _ROLE_KEYS:
        role = dump_model(color_system.get(role_key))
        if not role:
            continue
        candidates = {role_key, str(role.get("key") or ""), str(role.get("label") or "")}
        if lowered in {candidate.lower() for candidate in candidates if candidate}:
            hex_value = str(role.get("hex") or "").strip()
            if _HEX_RE.match(hex_value):
                return hex_value.upper()
        for variant in role.get("variants") or []:
            item = dump_model(variant)
            candidates = {str(item.get("name") or ""), f"{role_key}.{item.get('name', '')}", f"{role.get('label', role_key)} {item.get('name', '')}"}
            if lowered in {candidate.lower() for candidate in candidates if candidate.strip()}:
                hex_value = str(item.get("hex") or "").strip()
                if _HEX_RE.match(hex_value):
                    return hex_value.upper()

    return palette_lookup(brand).get(token, "")


def color_system_prompt_lines(brand: Any) -> list[str]:
    def _short(text: str, words: int = 3) -> str:
        parts = str(text or "").split()
        return " ".join(parts[:words])

    lines: list[str] = []
    color_system = color_system_data(brand)
    for role_key in _ROLE_KEYS:
        role = dump_model(color_system.get(role_key))
        if not role:
            continue
        label = str(role.get("label") or role_key).strip()
        base_hex = str(role.get("hex") or "").strip().upper()
        usage_hint = str(role.get("usage_hint") or "").strip()
        agent_hint = str(role.get("agent_hint") or "").strip()
        variant_bits = []
        for variant in role.get("variants") or []:
            item = dump_model(variant)
            name = str(item.get("name") or "").strip()
            hex_value = str(item.get("hex") or "").strip().upper()
            hint = _short(str(item.get("usage_hint") or "").strip())
            if name and hex_value:
                variant_bits.append(f"{name} {hex_value}" + (f" ({hint})" if hint else ""))
        detail = f"{label} ({role_key}) base {base_hex}"
        hints = "; ".join(part for part in (f"usage {_short(usage_hint)}" if usage_hint else "", f"agent {_short(agent_hint)}" if agent_hint else "") if part)
        if hints:
            detail += f" — {hints}"
        if variant_bits:
            detail += "; accepted variants: " + ", ".join(variant_bits)
        lines.append(detail)
    return lines


def color_system_config(brand: Any) -> dict[str, Any]:
    return color_system_data(brand)


__all__ = [
    "choose_role_color",
    "color_system_config",
    "color_system_data",
    "color_system_prompt_lines",
    "dump_model",
    "palette_lookup",
    "resolve_color_token",
]
