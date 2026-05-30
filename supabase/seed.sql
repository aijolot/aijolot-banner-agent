-- Aijolot Banner Agent — local seed data
-- Loaded by `supabase db reset` after migrations.

insert into public.placement_types
  (key, label, description, supported_targets, supported_slots, default_dimensions, config_schema)
values
  (
    'announcement_bar',
    'Barra de anuncios',
    'Short global promotional strip near the storefront header.',
    array['home', 'collection', 'product', 'page', 'store'],
    '[{"key":"announce","label":"Barra de anuncios"}, {"key":"after_header","label":"Después del header"}]',
    '{"desktop":{"width":1200,"height":48},"tablet":{"width":768,"height":48},"mobile":{"width":390,"height":56}}',
    '{}'
  ),
  (
    'hero_main',
    'Hero principal',
    'Primary above-the-fold marketing banner.',
    array['home', 'collection', 'page'],
    '[{"key":"hero","label":"Hero principal"}, {"key":"top","label":"Parte superior"}]',
    '{"desktop":{"width":1440,"height":420},"tablet":{"width":768,"height":360},"mobile":{"width":390,"height":460}}',
    '{}'
  ),
  (
    'promo_card',
    'Promo card',
    'Medium-sized promotional card inside homepage or grid sections.',
    array['home', 'collection'],
    '[{"key":"promo_l","label":"Promo izquierda"}, {"key":"promo_r","label":"Promo derecha"}, {"key":"coll_inline","label":"Bloque intermedio"}]',
    '{"desktop":{"width":600,"height":300},"tablet":{"width":384,"height":260},"mobile":{"width":390,"height":260}}',
    '{}'
  ),
  (
    'collection_header',
    'Cabecera de colección',
    'Collection page header banner.',
    array['collection'],
    '[{"key":"coll_top","label":"Cabecera de colección"}, {"key":"above_product_grid","label":"Sobre grid de productos"}]',
    '{"desktop":{"width":1440,"height":320},"tablet":{"width":768,"height":300},"mobile":{"width":390,"height":360}}',
    '{}'
  ),
  (
    'pdp_strip',
    'Franja de oferta PDP',
    'Product detail page offer strip.',
    array['product'],
    '[{"key":"pdp_strip","label":"Franja de oferta"}, {"key":"below_product_info","label":"Debajo de información de producto"}]',
    '{"desktop":{"width":520,"height":90},"tablet":{"width":520,"height":90},"mobile":{"width":390,"height":110}}',
    '{}'
  ),
  (
    'pdp_cross_sell',
    'Cross-sell PDP',
    'Cross-sell banner inside product detail pages.',
    array['product'],
    '[{"key":"pdp_cross","label":"Cross-sell"}]',
    '{"desktop":{"width":1200,"height":220},"tablet":{"width":768,"height":220},"mobile":{"width":390,"height":280}}',
    '{}'
  ),
  (
    'footer_cta',
    'CTA de footer',
    'Footer call-to-action banner.',
    array['home', 'collection', 'product', 'page', 'store'],
    '[{"key":"footer","label":"CTA de footer"}, {"key":"bottom","label":"Antes del footer"}]',
    '{"desktop":{"width":1200,"height":260},"tablet":{"width":768,"height":260},"mobile":{"width":390,"height":300}}',
    '{}'
  ),
  (
    'search_results_banner',
    'Banner de resultados de búsqueda',
    'Banner rendered on search result pages for a query trigger.',
    array['search'],
    '[{"key":"search_top","label":"Banner de resultados"}]',
    '{"desktop":{"width":1200,"height":200},"tablet":{"width":768,"height":200},"mobile":{"width":390,"height":240}}',
    '{}'
  )
on conflict (key) do update set
  label = excluded.label,
  description = excluded.description,
  supported_targets = excluded.supported_targets,
  supported_slots = excluded.supported_slots,
  default_dimensions = excluded.default_dimensions,
  config_schema = excluded.config_schema,
  is_active = true;

-- Demo team/store/brand without users. The app can attach authenticated users later.
insert into public.teams (id, name, slug)
values ('00000000-0000-0000-0000-000000000001', 'Aijolot Demo Team', 'aijolot-demo')
on conflict (slug) do update set name = excluded.name;

insert into public.stores
  (id, team_id, shop_domain, display_name, shopify_api_version, theme_id, status)
values
  ('00000000-0000-0000-0000-000000000101', '00000000-0000-0000-0000-000000000001', 'maison-store.myshopify.com', 'Maison Store', '2026-01', 'demo-theme', 'connected')
on conflict (team_id, shop_domain) do update set
  display_name = excluded.display_name,
  theme_id = excluded.theme_id,
  status = excluded.status;

insert into public.brand_contexts
  (id, team_id, store_id, name, slug, description, palette, typography, voice, allowed_rules, forbidden_rules, image_style_directives, logo_url)
values
  (
    '00000000-0000-0000-0000-000000000201',
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000101',
    'Maison / Hugo Boss Demo',
    'maison-hugo-boss-demo',
    'Seed brand context matching the current frontend prototype.',
    '[{"hex":"#0B1622","name":"Noir base"},{"hex":"#1E3A52","name":"Steel navy"},{"hex":"#C9A24B","name":"Boss gold"},{"hex":"#F5F2EC","name":"Ivory"},{"hex":"#B23A6B","name":"Rosé accent"}]',
    '{"display":"Space Grotesk","body":"Inter"}',
    '{"tone":["Profesional","Premium","Confiable","Directo","Sin exclamaciones"],"summary":"Segunda persona para acciones, neutral en descripciones. Calmado, confiado, sin ruido."}',
    array['Logo siempre en mayúsculas', 'Mínimo 1 frasco visible', 'CTA en contraste AA+', 'Sin degradados arcoíris'],
    array['Sin degradados arcoíris', 'Sin emojis', 'No distorsionar el frasco', 'No tapar el producto con texto'],
    'Premium fragrance photography, elegant lighting, product is sacred, no embedded text in generated image.',
    null
  )
on conflict (team_id, slug) do update set
  palette = excluded.palette,
  typography = excluded.typography,
  voice = excluded.voice,
  allowed_rules = excluded.allowed_rules,
  forbidden_rules = excluded.forbidden_rules,
  image_style_directives = excluded.image_style_directives;

insert into public.shopify_resource_cache
  (store_id, resource_type, shopify_gid, handle, title, vendor, tags, image_url, status, raw)
values
  ('00000000-0000-0000-0000-000000000101', 'collection', 'gid://shopify/Collection/1', 'fragancias', 'Fragancias', null, array['perfume', 'hugo-boss'], null, 'active', '{}'),
  ('00000000-0000-0000-0000-000000000101', 'collection', 'gid://shopify/Collection/2', 'hombre', 'Hombre', null, array['masculino'], null, 'active', '{}'),
  ('00000000-0000-0000-0000-000000000101', 'collection', 'gid://shopify/Collection/3', 'mujer', 'Mujer', null, array['femenino'], null, 'active', '{}'),
  ('00000000-0000-0000-0000-000000000101', 'product', 'gid://shopify/Product/1001', 'boss-bottled-edp-100ml', 'Boss Bottled EDP 100ml', 'Hugo Boss', array['fragancia','gender:male'], null, 'active', '{"sku":"HB-BOTTLED-100","stock":64,"price":138,"sale":124.2}'),
  ('00000000-0000-0000-0000-000000000101', 'product', 'gid://shopify/Product/1002', 'boss-alive-edp-80ml', 'Boss Alive EDP 80ml', 'Hugo Boss', array['fragancia','gender:female'], null, 'active', '{"sku":"HB-ALIVE-80","stock":51,"price":124,"sale":111.6}'),
  ('00000000-0000-0000-0000-000000000101', 'product', 'gid://shopify/Product/1003', 'set-lujo-boss-bottled', 'Set Lujo Boss Bottled', 'Hugo Boss', array['fragancia','vip:true'], null, 'active', '{"sku":"HB-SET-LUX","stock":12,"price":210,"sale":189}'),
  ('00000000-0000-0000-0000-000000000101', 'page', 'gid://shopify/Page/2001', 'promociones', 'Promociones', null, array['landing'], null, 'published', '{}')
on conflict (store_id, resource_type, shopify_gid) do update set
  handle = excluded.handle,
  title = excluded.title,
  vendor = excluded.vendor,
  tags = excluded.tags,
  raw = excluded.raw,
  synced_at = now();

insert into public.optimization_insights
  (team_id, tag, insight, lift_label, source)
values
  ('00000000-0000-0000-0000-000000000001', 'Calzado · primavera', 'Estructuras minimalistas + botón flotante en color contraste convirtieron 24% más.', '+24%', '{"seed":true}'),
  ('00000000-0000-0000-0000-000000000001', 'Perfumes · día de la madre', 'Frasco centrado con halo superó al layout split en mobile.', '+11%', '{"seed":true}'),
  ('00000000-0000-0000-0000-000000000001', 'VIP · histórico', 'Copys de exclusividad elevan CTR en segmento VIP.', '+37%', '{"seed":true}');
