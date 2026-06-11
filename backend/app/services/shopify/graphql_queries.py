"""Admin GraphQL query strings for live catalog reads (F3) and brand discovery."""

from __future__ import annotations

import re

# Shop/brand metadata for brand discovery. ``shop.brand`` needs a recent Admin
# API version + scope; callers retry with SHOP_BASIC_METADATA_QUERY when the
# brand query errors so discovery degrades to partial instead of failing.
SHOP_BRAND_METADATA_QUERY = """
query ShopBrandMetadata {
  shop {
    name
    primaryDomain { url host }
    brand {
      slogan
      shortDescription
      colors {
        primary { background foreground }
        secondary { background foreground }
      }
      logo { image { url } }
      squareLogo { image { url } }
      coverImage { image { url } }
    }
  }
}
"""

SHOP_BASIC_METADATA_QUERY = """
query ShopBasicMetadata {
  shop {
    name
    primaryDomain { url host }
  }
}
"""

PRODUCTS_QUERY = """
query Products($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query, sortKey: TITLE) {
    edges {
      cursor
      node {
        id
        handle
        title
        vendor
        status
        tags
        totalInventory
        featuredImage { url }
        priceRangeV2 { minVariantPrice { amount currencyCode } }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

COLLECTIONS_QUERY = """
query Collections($first: Int!, $after: String) {
  collections(first: $first, after: $after, sortKey: TITLE) {
    edges {
      cursor
      node {
        id
        handle
        title
        productsCount { count }
        image { url }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# Customer segments require read_customers / read_segments scope; callers wrap
# this in try/except and degrade gracefully when unavailable.
SEGMENTS_QUERY = """
query Segments($first: Int!, $after: String) {
  segments(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        name
        query
        creationDate
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


def handleize(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "untitled"


def product_to_row(node: dict) -> dict:
    price = None
    prv = node.get("priceRangeV2") or {}
    minv = (prv.get("minVariantPrice") or {})
    if minv.get("amount") is not None:
        price = minv.get("amount")
    return {
        "shopify_gid": node.get("id"),
        "handle": node.get("handle"),
        "title": node.get("title") or node.get("handle") or "Untitled",
        "vendor": node.get("vendor"),
        "tags": node.get("tags") or [],
        "image_url": (node.get("featuredImage") or {}).get("url"),
        "status": (node.get("status") or "").lower() or None,
        "raw": {
            "price": price,
            "currency": minv.get("currencyCode"),
            "total_inventory": node.get("totalInventory"),
        },
    }


def collection_to_row(node: dict) -> dict:
    count = node.get("productsCount")
    if isinstance(count, dict):
        count = count.get("count")
    return {
        "shopify_gid": node.get("id"),
        "handle": node.get("handle"),
        "title": node.get("title") or node.get("handle") or "Untitled",
        "vendor": None,
        "tags": [],
        "image_url": (node.get("image") or {}).get("url"),
        "status": "active",
        "raw": {"products_count": count},
    }


def vendor_to_row(vendor: str) -> dict:
    handle = handleize(vendor)
    return {
        "shopify_gid": f"vendor:{handle}",
        "handle": handle,
        "title": vendor,
        "vendor": vendor,
        "tags": [],
        "image_url": None,
        "status": "active",
        "raw": {"derived": "products.vendor"},
    }


def segment_to_row(node: dict) -> dict:
    name = node.get("name") or "Segment"
    return {
        "shopify_gid": node.get("id") or f"segment:{handleize(name)}",
        "handle": handleize(name),
        "title": name,
        "vendor": None,
        "tags": [],
        "image_url": None,
        "status": "active",
        "raw": {"query": node.get("query"), "creation_date": node.get("creationDate")},
    }
