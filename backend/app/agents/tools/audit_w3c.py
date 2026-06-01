from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

_REQUIRED_TAGS = ("html", "head", "body", "title", "meta")


class _SimpleHTMLAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: list[str] = []
        self.images: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.meta_names: set[str] = set()
        self.meta_props: set[str] = set()
        self.h1_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: v or "" for k, v in attrs}
        self.tags.append(tag)
        if data.get("id"):
            self.ids.append(data["id"])
        if tag == "img":
            self.images.append(data)
        if tag == "a":
            self.links.append(data)
        if tag == "meta":
            if data.get("name"):
                self.meta_names.add(data["name"].lower())
            if data.get("property"):
                self.meta_props.add(data["property"].lower())
        if tag == "h1":
            self.h1_count += 1


async def validate(html: str) -> dict[str, Any]:
    """Return deterministic W3C-ish validation without external services."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not html or not html.strip():
        return {"valid": False, "errors": [{"code": "empty_html", "message": "HTML is empty"}], "warnings": []}
    if not re.match(r"\s*<!doctype html>", html, re.I):
        warnings.append({"code": "doctype_missing", "message": "Expected <!doctype html> declaration", "severity": "warn"})

    parser = _SimpleHTMLAuditParser()
    try:
        parser.feed(html)
    except Exception as exc:  # pragma: no cover - HTMLParser rarely raises
        errors.append({"code": "parse_error", "message": str(exc), "severity": "fail"})

    tags = set(parser.tags)
    for tag in _REQUIRED_TAGS:
        if tag not in tags:
            errors.append({"code": f"missing_{tag}", "message": f"Missing <{tag}> element", "severity": "fail"})
    if "viewport" not in parser.meta_names:
        warnings.append({"code": "missing_viewport", "message": "Missing responsive viewport meta tag", "severity": "warn"})
    if parser.h1_count != 1:
        warnings.append({"code": "h1_count", "message": f"Expected exactly one h1, found {parser.h1_count}", "severity": "warn"})
    if len(parser.ids) != len(set(parser.ids)):
        errors.append({"code": "duplicate_ids", "message": "Duplicate id attributes found", "severity": "fail"})
    for index, image in enumerate(parser.images):
        if "alt" not in image:
            errors.append({"code": "img_alt_missing", "message": f"Image {index} missing alt attribute", "severity": "fail"})
    for index, link in enumerate(parser.links):
        if not link.get("href"):
            warnings.append({"code": "anchor_href_missing", "message": f"Anchor {index} missing href", "severity": "warn"})
    return {"valid": not errors, "errors": errors, "warnings": warnings, "summary": f"{len(errors)} errors, {len(warnings)} warnings"}
