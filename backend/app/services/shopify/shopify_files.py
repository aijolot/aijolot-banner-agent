"""Host banner assets on Shopify Files for real (non-dry-run) publishing.

The rendered banner image is stored in our Supabase bucket. Its public URL is
reachable from our own preview, but on a live Shopify storefront a visitor's
browser must fetch the image from a publicly-reachable CDN — a localhost / private
Supabase URL would 404 for them. So at real-publish time we re-host the image on
Shopify Files (their CDN) and rewrite the campaign config to point at that URL.

Flow (Admin GraphQL):
  1. stagedUploadsCreate  → a signed upload target + form parameters
  2. multipart POST bytes → the signed target (no Shopify token; it's GCS/S3)
  3. fileCreate           → register the uploaded resource as a File
  4. poll node(id)        → wait for MediaImage.image.url (the CDN URL)

Everything is best-effort: if any step fails we keep the original URL and let the
publish proceed (the banner copy/background still render; only the image is absent),
rather than failing the whole publish.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

import httpx

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "kong", "host.docker.internal"}

_STAGED_UPLOADS_CREATE = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""

_FILE_CREATE = """
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus alt ... on MediaImage { image { url } } }
    userErrors { field message }
  }
}
"""

_NODE_IMAGE = """
query fileUrl($id: ID!) {
  node(id: $id) {
    ... on MediaImage { id fileStatus image { url } }
  }
}
"""


def is_local_asset_url(url: str, *, extra_hosts: set[str] | None = None) -> bool:
    """True when the URL points at a host a public storefront cannot reach."""
    if not url or not isinstance(url, str):
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    if host in _LOCAL_HOSTS or (extra_hosts and host in extra_hosts):
        return True
    # RFC1918 / loopback ranges that a public browser can't fetch.
    return host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.")) or host.endswith(".local")


def _mime_for(url: str) -> str:
    lower = url.lower().split("?")[0]
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".avif"):
        return "image/avif"
    return "image/webp"


def _filename_for(url: str) -> str:
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1] if path else "banner.webp"
    return name or "banner.webp"


def upload_bytes_to_files(
    client: Any,
    *,
    data: bytes,
    filename: str,
    mime_type: str,
    poll: int = 6,
    http_post: Callable[[str, dict[str, Any], bytes, str, str], None] | None = None,
) -> str | None:
    """Stage + create a File and return its CDN URL, or None on any failure."""

    staged = client.graphql(
        _STAGED_UPLOADS_CREATE,
        {
            "input": [
                {
                    "resource": "FILE",
                    "filename": filename,
                    "mimeType": mime_type,
                    "httpMethod": "POST",
                    "fileSize": str(len(data)),
                }
            ]
        },
    )
    block = (staged.get("stagedUploadsCreate") or {})
    if block.get("userErrors"):
        return None
    targets = block.get("stagedTargets") or []
    if not targets:
        return None
    target = targets[0]
    upload_url = target.get("url")
    resource_url = target.get("resourceUrl")
    params = {p["name"]: p["value"] for p in (target.get("parameters") or []) if p.get("name")}
    if not upload_url or not resource_url:
        return None

    poster = http_post or _default_multipart_post
    poster(upload_url, params, data, filename, mime_type)

    created = client.graphql(
        _FILE_CREATE,
        {"files": [{"originalSource": resource_url, "contentType": "IMAGE", "alt": filename}]},
    )
    fblock = created.get("fileCreate") or {}
    if fblock.get("userErrors"):
        return None
    files = fblock.get("files") or []
    if not files:
        return None
    first = files[0]
    url = ((first.get("image") or {}) or {}).get("url")
    if url:
        return str(url)

    # File registered but the CDN URL is not ready yet — poll node(id).
    file_id = first.get("id")
    for _ in range(max(0, poll)):
        node = client.graphql(_NODE_IMAGE, {"id": file_id}).get("node") or {}
        url = ((node.get("image") or {}) or {}).get("url")
        if url:
            return str(url)
        if node.get("fileStatus") == "FAILED":
            return None
    return None


def _default_multipart_post(upload_url: str, params: dict[str, Any], data: bytes, filename: str, mime_type: str) -> None:
    form = {k: (None, v) for k, v in params.items()}
    form["file"] = (filename, data, mime_type)
    with httpx.Client(timeout=30.0) as http:
        response = http.post(upload_url, files=form)
    if response.status_code >= 400:
        from app.services.shopify.client import ShopifyApiError

        raise ShopifyApiError(f"staged upload failed with status {response.status_code}")


def rehost_config_assets(
    client: Any,
    config: dict[str, Any],
    *,
    fetch_bytes: Callable[[str], bytes | None],
    extra_hosts: set[str] | None = None,
    http_post: Callable[[str, dict[str, Any], bytes, str, str], None] | None = None,
) -> dict[str, Any]:
    """Return a copy of ``config`` with locally-hosted image URLs swapped for Shopify
    Files CDN URLs. Best-effort: an asset that can't be fetched/uploaded keeps its
    original URL. Records what was rehosted under ``config['asset_hosting']``.
    """

    out = dict(config)
    rehosted: list[dict[str, str]] = []
    cache: dict[str, str] = {}

    def _resolve(url: str) -> str:
        if not is_local_asset_url(url, extra_hosts=extra_hosts):
            return url
        if url in cache:
            return cache[url]
        data = None
        try:
            data = fetch_bytes(url)
        except Exception:  # noqa: BLE001 — best-effort rehost
            data = None
        if not data:
            return url
        cdn = None
        try:
            cdn = upload_bytes_to_files(
                client, data=data, filename=_filename_for(url), mime_type=_mime_for(url), http_post=http_post
            )
        except Exception:  # noqa: BLE001 — keep original on any Files failure
            cdn = None
        if not cdn:
            return url
        cache[url] = cdn
        rehosted.append({"from": url, "to": cdn})
        return cdn

    image = out.get("image")
    if isinstance(image, dict) and image.get("url"):
        new_url = _resolve(str(image["url"]))
        if new_url != image["url"]:
            out["image"] = {**image, "url": new_url}

    if rehosted:
        out["asset_hosting"] = {"provider": "shopify_files", "rehosted": rehosted}
    return out


__all__ = ["is_local_asset_url", "upload_bytes_to_files", "rehost_config_assets"]
