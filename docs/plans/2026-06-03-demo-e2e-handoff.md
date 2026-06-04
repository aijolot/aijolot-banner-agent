# Handoff — "dejar la demo funcional end-to-end" (2026-06-03)

## Cómo retomar en una sesión nueva
1. Lee el **plan maestro** (12 fases, mapeo de las 11 mejoras del usuario):
   `/Users/gabriel_ormo/.claude/plans/vamos-planeando-el-dejar-abundant-dusk.md`
2. Lee este handoff.
3. Estás en la rama `feat/demo-functional-e2e`. Working tree limpio.
4. Continúa por **F5** (generación real) — ver "Próximo paso".

## Estado git
- Rama: `feat/demo-functional-e2e` (sobre `main`).
- Commits (más reciente primero):
  - `fadcd02` F10 publisher seguro + dry-run + install-theme (código; e2e pendiente F5)
  - `ce8ced9` F4 placeholders Liquid + mapeo placement→anchor
  - `f915a6c` F3 lecturas Shopify live + sync + resource_types
  - `c95afe8` F2 fix loop del brief (intake Gemini)
  - `e53da74` F1 KG ingest + retrieval tiered
  - `3339329` F0 fundaciones
  - `88f1f14` fix previo (generation_events NULL en batch)
- Sin PR todavía (el usuario pidió "solo commit, aún no PR").

## Fases hechas (✅) vs pendientes (⬜)
- ✅ F0 Fundaciones · F1 KG · F2 Brief · F3 Lecturas live · F4 Placeholders · F5 Generación real · F10 código publisher
- ⬜ F6 concept+layout KG · F7 fondos AI · F8 prompts descriptivos+modelos · F9 refine agéntico · F11 frontend · F12 verificación final
- ⬜ **F10 e2e** (publish real de una campaña) — ya desbloqueado por F5; falta correr schedule→dry-run publish→publish real→storefront.

## F5 — hecho (2026-06-03)
- Nuevo `backend/app/services/banners/run_orchestrator.py` (`RunOrchestrator`): ejecuta load_brand→intake→personalization→best-practices→concept→image→optimize→render(html+liquid)→audit nodo por nodo; persiste `campaign_revision`+`banner_variants`(default)+`banner_layout_variants`(A/B/C)+`audit_reports`+preview en Supabase Storage; promueve draft→selected al terminar (un fallo deja un draft inerte, no contamina la selección).
- `generation_run_service.start_generation_run`: ramifica al orquestador cuando hay orquestador inyectado (`from_supabase_client`) + `run_type=initial`. Refinement sigue determinista (lo dueña RevisionService → F9). Path determinista intacto (`task-10-deterministic`) para tests/in-memory. `GenerationRunRepository.update` añadido (running→succeeded/failed). `_run_coro` corre el orquestador async desde el handler sync (rutas son `def` → threadpool → sin loop activo → `asyncio.run` seguro).
- Imagen: cost_guard solo reserva para provider real; sin key o `ImageProviderUnavailable` → cae a `FakeImageProvider` (gratis) → el banner siempre renderiza.
- Gotcha: assets de Supabase traen `UploadResponse` (no JSON-serializable) que rompía `liquid_payload_builder` (`json.dumps(config)`) y writes jsonb → `_json_safe` saneando en la frontera tras optimizar.
- Verificado e2e (campaña `a1cf2aee-…`): 18 eventos reales/nodo, html 5919B, imagen Gemini real ($0.04/run), audit warn, supersede/promote correctos. Tests: **295 passed, 3 skipped** (entorno limpio).
- ⚠️ El backend del handoff arrancaba **sin `--reload`** → hay que reiniciar uvicorn para cargar cambios.

## Entorno / cómo correr (CRÍTICO)
- Backend: `cd backend && set -a && . ../.env; set +a; .venv/bin/uvicorn app.main:app --reload --port 8000 --host 127.0.0.1`. venv es Python 3.11.
- Frontend estático: `python3 -m http.server 5500 --directory frontend` (default API base `http://localhost:8000`).
- Supabase local en `:55321` (Docker). Migraciones nuevas se aplicaron con `psql "postgresql://postgres:postgres@127.0.0.1:55322/postgres" -f <migracion>` SIN reset (para no borrar datos).
- **Tests: correr SIN sourcear `.env`** (entorno limpio, como CI):
  `env -i PATH="$PATH" HOME="$HOME" .venv/bin/python -m pytest -q`  → 291 passed, 3 skipped.
  Con `.env` cargado, los tests de fallback in-memory fallan porque ven Supabase configurado.
- Demo auth headers (frontend ya los manda): `X-Aijolot-User-Id: …601`, `Team-Id: …001`, `Store-Id: …101`, `Authorization: Bearer demo:601:001:101` (UUIDs completos).

## Decisiones del usuario (fijadas)
- Tienda Shopify **real** (no simulado): lecturas live + placeholders + publish real.
- Las **11 mejoras** completas, por fases según dependencia.
- Modelos/usage-shot vía **prompts descriptivos primero** (proponer → elegir → generar).
- Principio rector: **no romper caminos deterministas**. Cada rama Gemini se activa por flag (`AIJOLOT_*_PROVIDER=gemini`) + key, y cae a determinista ante `GeminiUnavailable`/cost cap.

## Hallazgos / gotchas importantes
- `.env` ahora tiene: `GOOGLE_API_KEY` (AI Studio), `AIJOLOT_INTAKE_PROVIDER=gemini`, `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`, `KG_EMBEDDINGS_ENABLED` (default false; setear `true` para retrieval vectorial), `SHOPIFY_*` reales, `SHOPIFY_PUBLISH_DRY_RUN=true`.
- **Embeddings**: `text-embedding-005` NO existe en la API de AI Studio → usamos `gemini-embedding-001` (768 dims). Default ya cambiado en settings + gemini_embed.
- **Token Shopify**: tenía typo `sshpat_` (39 chars) → corregido a `shpat_` (38). Conexión OK contra `aijolo-demo.myshopify.com`, theme `188324807026`.
- **KG sembrado**: 71 docs en `kg_documents` con embeddings. Re-seed: `python scripts/kg_seed.py` (dry-run con `--dry-run`).
- **Store demo alineado**: el row `…101` ahora apunta a `aijolo-demo.myshopify.com` / theme `188324807026` (UPDATE manual en DB local; ojo si se hace `supabase db reset` se revierte al seed `maison-store`).
- **Placeholders instalados** en el tema dev real: 10 assets `aijolot-*` (section + block + 8 anchors). Idempotente vía `put_theme_asset`.
- **Generación hoy es determinista**: `generation_run_service.start_generation_run` devuelve `succeeded` con eventos fake; NO persiste revisión/variants/preview/audit. Eso es lo que arregla F5.

## Próximo paso — F5 (generación real)
Objetivo: que `start_generation_run` ejecute un pipeline Gemini-backed (acotado) que persista `campaign_revision` + `banner_variants` + `banner_layout_variants` + `html_preview`/`preview_storage_path` + `audit_reports`, emitiendo eventos reales por nodo; conservar fallback determinista sin key/cost.
- Reusar `app/workflows/banner_creation.py:run_to_audit` (render HTML/Liquid + audit reales), ejecutando nodo a nodo.
- Crear `app/services/banners/run_orchestrator.py`; reemplazar el cuerpo `task-10-deterministic` de `start_generation_run` (`generation_run_service.py:141`).
- Skills a encadenar: best-practices-retrieve → banner-concept-draft → image-prompt-refine → nano-banana-image-generate → image-asset-optimize → banner-html-seo-render → liquid-section-build → performance-audit.
- Imagen hard-capped 1/run tras `cost_guard`; degrada a fake provider sin key.
- Tras F5: verificar publish e2e de F10 (campaña → generate → ready-for-review → approve → schedule → dry-run publish → real publish → ver banner en storefront).

## Verificación rápida que ya pasa (curl, backend en :8000)
- Intake: `POST /api/v1/campaigns/intake {"message":"Promo de fin de semana para mujeres jóvenes, botón Comprar ya, en el hero"}` → brief completo en 1 turno.
- Sync live: `POST /api/v1/stores/00000000-0000-0000-0000-000000000101/shopify/sync {"dry_run":true}` → counts reales.
- Search: `GET /api/v1/stores/…101/shopify/resources?resource_type=product&q=212%20vip`.
- Install theme (dry): `POST /api/v1/stores/…101/shopify/install-theme-files`.
