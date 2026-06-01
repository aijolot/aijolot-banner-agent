from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx


class ShopifyApiError(Exception):
    pass


class ShopifyThemeClient(Protocol):
    def put_theme_asset(self, *, theme_id: str, key: str, value: str) -> dict[str, Any]: ...
    def get_shop_metafield(self, *, namespace: str, key: str) -> dict[str, Any] | None: ...
    def put_shop_metafield(self, *, namespace: str, key: str, value: str, type: str = "json") -> dict[str, Any]: ...
    def delete_shop_metafield(self, *, namespace: str, key: str) -> dict[str, Any]: ...


class ShopifyAdminClient:
    def __init__(self, *, shop_domain: str, access_token: str, api_version: str = "2026-01", timeout: float = 20.0) -> None:
        if not shop_domain or not access_token:
            raise ValueError("shop_domain and access_token are required")
        self.shop_domain = self._normalize_shop_domain(shop_domain)
        self.access_token = access_token
        self.api_version = api_version
        self.timeout = timeout

    @staticmethod
    def _normalize_shop_domain(shop_domain: str) -> str:
        domain = shop_domain.removeprefix("https://").removeprefix("http://").strip("/").lower()
        if "/" in domain or "@" in domain or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", domain):
            raise ValueError("shop_domain must be a safe *.myshopify.com host")
        return domain

    @property
    def base_url(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{self.api_version}"

    def put_theme_asset(self, *, theme_id: str, key: str, value: str) -> dict[str, Any]:
        payload = {"asset": {"key": key, "value": value}}
        return self._request("PUT", f"/themes/{theme_id}/assets.json", json=payload).get("asset", {})

    def get_shop_metafield(self, *, namespace: str, key: str) -> dict[str, Any] | None:
        response = self._request("GET", "/metafields.json", params={"namespace": namespace, "key": key, "owner_resource": "shop"})
        metafields = response.get("metafields") or []
        return dict(metafields[0]) if metafields else None

    def put_shop_metafield(self, *, namespace: str, key: str, value: str, type: str = "json") -> dict[str, Any]:
        existing = self.get_shop_metafield(namespace=namespace, key=key)
        payload = {"metafield": {"namespace": namespace, "key": key, "value": value, "type": type, "owner_resource": "shop"}}
        if existing and existing.get("id"):
            payload["metafield"] = {"id": existing["id"], "value": value, "type": type}
            return self._request("PUT", f"/metafields/{existing['id']}.json", json=payload).get("metafield", {})
        return self._request("POST", "/metafields.json", json=payload).get("metafield", {})

    def delete_shop_metafield(self, *, namespace: str, key: str) -> dict[str, Any]:
        # REST delete requires a metafield id. For demo safety, publish an empty JSON array instead.
        self.put_shop_metafield(namespace=namespace, key=key, value=json.dumps([]), type="json")
        return {"deleted": False, "cleared": True}

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"X-Shopify-Access-Token": self.access_token, "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, f"{self.base_url}{path}", headers=headers, json=json, params=params)
        if response.status_code >= 400:
            raise ShopifyApiError(f"Shopify API request failed with status {response.status_code}")
        return response.json() if response.content else {}
