-- KG vector-similarity RPC + idempotent-seed unique index.
-- Complements 20260529000000_kg_pgvector.sql (which only added an ivfflat index).
-- Embedding model: text-embedding-005 (768 dims, cosine).

-- Idempotent seeding: one row per (kind, title, brand_id), treating NULL brand
-- as the empty string so global docs collapse to a single row.
create unique index if not exists kg_documents_identity_uidx
  on public.kg_documents (kind, title, coalesce(brand_id, ''));

-- Cosine-similarity retrieval. Score = 1 - cosine_distance (higher = closer).
-- Filters by kind set and brand (NULL brand rows are always eligible).
create or replace function public.match_kg_documents(
  query_embedding vector(768),
  match_kinds text[] default null,
  match_brand_id text default null,
  match_count int default 5
)
returns table (
  id uuid,
  kind text,
  title text,
  body text,
  metadata jsonb,
  brand_id text,
  score double precision
)
language sql
stable
security definer
set search_path = public
as $$
  select
    d.id,
    d.kind,
    d.title,
    d.body,
    d.metadata,
    d.brand_id,
    (1 - (d.embedding <=> query_embedding))::double precision as score
  from public.kg_documents d
  where (match_kinds is null or d.kind = any(match_kinds))
    and (match_brand_id is null or d.brand_id is null or d.brand_id = match_brand_id)
  order by d.embedding <=> query_embedding
  limit greatest(1, coalesce(match_count, 5));
$$;

grant execute on function public.match_kg_documents(vector, text[], text, int) to anon, authenticated, service_role;

comment on function public.match_kg_documents is
  'Cosine KG retrieval for the banner agent. Returns top matches with score in [0,1].';
