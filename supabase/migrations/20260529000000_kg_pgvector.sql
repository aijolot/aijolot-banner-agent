-- Knowledge graph for the Banner Agent (vector RAG via pgvector).
-- Lands per GH-NEW4. Embedding model: text-embedding-005 (768 dims).

create extension if not exists vector;

create table public.kg_documents (
  id           uuid primary key default gen_random_uuid(),
  kind         text not null check (kind in (
                 'best_practice',
                 'brand_example',
                 'liquid_pattern',
                 'audit_failure',
                 'prior_banner',
                 'seo_pattern'
               )),
  title        text not null,
  body         text not null,
  metadata     jsonb not null default '{}'::jsonb,
  embedding    vector(768) not null,
  brand_id     text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index kg_documents_embedding_idx
  on public.kg_documents
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 50);

create index kg_documents_kind_idx     on public.kg_documents (kind);
create index kg_documents_brand_idx    on public.kg_documents (brand_id);
create index kg_documents_metadata_gin on public.kg_documents using gin (metadata);

-- RLS: kg_documents are global reference data; only service role writes.
alter table public.kg_documents enable row level security;

create policy "kg_documents_read_all" on public.kg_documents
  for select using (true);

create policy "kg_documents_service_write" on public.kg_documents
  for all using (auth.role() = 'service_role')
            with check (auth.role() = 'service_role');

comment on table public.kg_documents is
  'Vector RAG knowledge graph for banner agent. Seed via scripts/kg_seed.py.';
