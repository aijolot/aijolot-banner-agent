from __future__ import annotations

import json
import re
from typing import Any

_SCRIPT_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)


async def validate(html: str) -> dict[str, Any]:
    """Validate presence and minimal shape of JSON-LD schema markup."""
    errors: list[dict[str, str]] = []
    schemas: list[dict[str, Any]] = []
    for match in _SCRIPT_RE.finditer(html or ""):
        raw = match.group(1).strip()
        # Preview renderer HTML-escapes JSON text minimally for safety.
        raw = raw.replace("&quot;", '"').replace("&amp;", "&")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append({"code": "json_ld_parse_error", "message": str(exc), "severity": "fail"})
            continue
        if isinstance(parsed, dict):
            schemas.append(parsed)
        elif isinstance(parsed, list):
            schemas.extend(item for item in parsed if isinstance(item, dict))
    if not schemas:
        errors.append({"code": "json_ld_missing", "message": "No application/ld+json script found", "severity": "fail"})
    supported = {"Offer", "Product", "PromotionCard", "WebPage"}
    schema_type = None
    for schema in schemas:
        schema_type = schema.get("@type") or schema_type
        if not schema.get("@context"):
            errors.append({"code": "schema_context_missing", "message": "JSON-LD missing @context", "severity": "fail"})
        if not schema.get("@type"):
            errors.append({"code": "schema_type_missing", "message": "JSON-LD missing @type", "severity": "fail"})
        if schema.get("@type") in supported and not (schema.get("name") or schema.get("description")):
            errors.append({"code": "schema_name_missing", "message": "Schema missing name/description", "severity": "fail"})
    return {"valid": not errors, "type": schema_type, "schemas": schemas, "errors": errors}
