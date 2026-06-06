-- Extend shopify_resource_cache to cache vendors ("marcas") and customer
-- segments synced from the Shopify Admin API (F3 live reads).
-- Vendors have no native GID; we synthesize shopify_gid = 'vendor:<handle>'.

alter table public.shopify_resource_cache
  drop constraint if exists shopify_resource_cache_resource_type_check;

alter table public.shopify_resource_cache
  add constraint shopify_resource_cache_resource_type_check
  check (resource_type in ('collection', 'product', 'page', 'vendor', 'customer_segment'));
