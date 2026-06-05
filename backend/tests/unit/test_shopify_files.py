"""Asset re-hosting on Shopify Files for real publish."""

from __future__ import annotations

from typing import Any

from app.services.shopify import shopify_files


class _FakeFilesClient:
    """Scripts the 3 GraphQL calls: stagedUploadsCreate, fileCreate, node poll."""

    def __init__(self, *, ready_inline: bool = True, fail_create: bool = False) -> None:
        self.ready_inline = ready_inline
        self.fail_create = fail_create
        self.calls: list[str] = []
        self._poll_calls = 0

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        if "stagedUploadsCreate" in query:
            self.calls.append("stage")
            return {
                "stagedUploadsCreate": {
                    "stagedTargets": [
                        {
                            "url": "https://shopify-staged-uploads.storage.googleapis.com/up",
                            "resourceUrl": "https://shopify-staged-uploads.storage.googleapis.com/up/banner.webp",
                            "parameters": [{"name": "key", "value": "up/banner.webp"}],
                        }
                    ],
                    "userErrors": [],
                }
            }
        if "fileCreate" in query:
            self.calls.append("create")
            if self.fail_create:
                return {"fileCreate": {"files": [], "userErrors": [{"message": "boom"}]}}
            image = {"url": "https://cdn.shopify.com/s/files/banner.webp"} if self.ready_inline else None
            return {"fileCreate": {"files": [{"id": "gid://shopify/MediaImage/1", "image": image}], "userErrors": []}}
        if "node" in query:
            self._poll_calls += 1
            self.calls.append("poll")
            # Becomes ready on the 2nd poll.
            image = {"url": "https://cdn.shopify.com/s/files/banner.webp"} if self._poll_calls >= 2 else None
            return {"node": {"id": variables["id"], "fileStatus": "READY" if image else "PROCESSING", "image": image}}
        raise AssertionError("unexpected query")


def _post_ok(url: str, params: dict[str, Any], data: bytes, filename: str, mime: str) -> None:
    return None


def test_is_local_asset_url() -> None:
    assert shopify_files.is_local_asset_url("http://127.0.0.1:55321/storage/x.webp")
    assert shopify_files.is_local_asset_url("http://localhost:9000/x.png")
    assert shopify_files.is_local_asset_url("http://192.168.1.5/x.webp")
    assert not shopify_files.is_local_asset_url("https://cdn.shopify.com/x.webp")
    assert not shopify_files.is_local_asset_url("https://abc.supabase.co/storage/x.webp")
    assert not shopify_files.is_local_asset_url("")


def test_upload_returns_cdn_url_inline() -> None:
    client = _FakeFilesClient(ready_inline=True)
    url = shopify_files.upload_bytes_to_files(
        client, data=b"img", filename="banner.webp", mime_type="image/webp", http_post=_post_ok
    )
    assert url == "https://cdn.shopify.com/s/files/banner.webp"
    assert client.calls == ["stage", "create"]


def test_upload_polls_until_ready() -> None:
    client = _FakeFilesClient(ready_inline=False)
    url = shopify_files.upload_bytes_to_files(
        client, data=b"img", filename="banner.webp", mime_type="image/webp", http_post=_post_ok
    )
    assert url == "https://cdn.shopify.com/s/files/banner.webp"
    assert client.calls.count("poll") >= 2


def test_upload_returns_none_on_filecreate_error() -> None:
    client = _FakeFilesClient(fail_create=True)
    url = shopify_files.upload_bytes_to_files(
        client, data=b"img", filename="banner.webp", mime_type="image/webp", http_post=_post_ok
    )
    assert url is None


def test_rehost_swaps_local_image_only() -> None:
    client = _FakeFilesClient(ready_inline=True)
    config = {"image": {"url": "http://127.0.0.1:55321/storage/v1/object/public/x/banner.webp", "alt": "a"}}
    out = shopify_files.rehost_config_assets(
        client, config, fetch_bytes=lambda url: b"bytes", http_post=_post_ok
    )
    assert out["image"]["url"] == "https://cdn.shopify.com/s/files/banner.webp"
    assert out["image"]["alt"] == "a"  # other fields preserved
    assert out["asset_hosting"]["provider"] == "shopify_files"


def test_rehost_leaves_public_url_untouched() -> None:
    client = _FakeFilesClient(ready_inline=True)
    config = {"image": {"url": "https://cdn.shopify.com/already.webp"}}
    out = shopify_files.rehost_config_assets(client, config, fetch_bytes=lambda url: b"x")
    assert out["image"]["url"] == "https://cdn.shopify.com/already.webp"
    assert "asset_hosting" not in out
    assert client.calls == []  # never touched Shopify


def test_rehost_keeps_original_when_fetch_fails() -> None:
    client = _FakeFilesClient(ready_inline=True)
    config = {"image": {"url": "http://127.0.0.1:55321/x/banner.webp"}}
    out = shopify_files.rehost_config_assets(client, config, fetch_bytes=lambda url: None)
    assert out["image"]["url"] == "http://127.0.0.1:55321/x/banner.webp"
    assert "asset_hosting" not in out
