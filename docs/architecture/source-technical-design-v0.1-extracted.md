# Extracted source: Aijolot Shopify Banner Agent Technical Design v0.1

Source PDF: `/Users/pk/Downloads/Aijolot-Shopify Banner Agent — Technical Design (Hackathon v0.1)-290526-031138.pdf`

Pages: 8


---

## Page 1

Shopify Banner Agent — Technical Design (Hackathon v0.1)
Shopify Banner Agent — Technical Design
Status:DRAFTService Line:AI AGENTSSprint: Hackathon 5 días   Epic:
1. Objetivo y alcance
Agente conversacional multi-step en Google ADK (Python) que asiste a admins de tiendas
Shopify a producir banners HTML responsivos, SEO-optimizados, con imagen generada por
Vertex AI, personalizables por customer.tags vía Shopify Sections + Liquid, y
publicables/scheduleables vía Supabase pg_cron y Shopify Admin API. HITL obligatorio antes
de publicar.
Out of scope (explícito)
Multi-idioma del banner.
A/B testing automático de variantes.
Analytics post-publish (CTR, conversion) — Optimization phase.
Multi-theme switching dinámico.
Edición visual WYSIWYG.
Librería histórica / gestión de banners pasados.
Regeneración periódica automática.
2. Stack y decisiones técnicas
GH-1
Documento de Technical Design producido por aijolot-design-execution a partir
de un Discovery Brief validado. Es un blueprint, no implementación. Aprobación humana
requerida antes de pasar a ejecución de sprint.
Agent framework Google ADK (Python) Closed list AIjolot (Google
Cloud Managed Agents)
LLM Gemini 2.5 Pro (creative) /
Flash (rápidos)
Costo/latencia balanceados
Image gen Imagen 4 (Vertex) o Gemini
2.5 Image
Pendiente — Spike GH-2 /
Decision GH-25
Capa Tecnología Decisión


---

## Page 2

3. Arquitectura — Graph del Agente
El agente está modelado como un graph de 12 nodos con un único punto HITL (nodo 10) y
branching en nodo 11 (immediate vs scheduled).
Error loading the extension!
Mermaid
Schedule storage Supabase + pg_cron Cliente dijo "cron en
Supabase"
Personalización Shopify Sections (Liquid) +
customer.tags
Render server-side, sin JS
extra
Brand context Markdown skill-format en repoPortable, versionable, multi-
tienda
HITL UI Streamlit Rápido para Python + ADK
Observabilidad ADK trace + Cloud Logging +
Supabase audit_log
Estándar AIjolot
Audit tooling html5validator + lighthouse-ci
+ schema-validator
Validables programáticamente
1flowchart TD2 Start([START]) --> N1[1. load_brand_context]3 N1 --> N2[2. intake_campaign_idea]4 N2 --> N3[3. capture_user_personalization]5 N3 --> N4[4. research_best_practices]6 N4 --> N5[5. draft_banner_concept]7 N5 --> N6[6. generate_image - Vertex AI]8 N6 --> N7[7. optimize_assets - WebP/AVIF/srcset]9 N7 --> N8[8. render_html + meta + JSON-LD + Liquid]10 N8 --> N9{9. audit - Lighthouse + W3C + Schema}11 N9 -- FAIL max 2x --> N512 N9 -- PASS --> N10{{10. human_review HITL}}13 N10 -- reject --> N514 N10 -- approved --> N11{11. schedule_or_publish}15 N11 -- immediate --> N12[12. publish_to_shopify - Admin API]16 N11 -- scheduled --> SB[(Supabase scheduled_banners)]17 SB -- pg_cron 1min --> N1218 N12 --> End([END - published])1920 style N10 fill:#fef3c7,stroke:#f59e0b21 style N9 fill:#dbeafe,stroke:#3b82f622 style SB fill:#dcfce7,stroke:#16a34a23


---

## Page 3

4. Contracts I/O por nodo
[1] load_brand_context
In:brand_id: str Out:BrandContext {name, palette, typography,
voice{tone, prohibited_words[], required_phrases[]}, logo_url,
image_style_directives, shopify{store_domain, theme_id}}
[2] intake_campaign_idea
In: user turn (free-form)   Out:Campaign {goal, audience, cta, tone, urgency,
placement, deadline?} LLM: Gemini Flash + structured output
[3] capture_user_personalization
Out:Variants: list[Variant {customer_tag, intent_delta, copy_override?}]
[4] research_best_practices
D1 estático (cheatsheet en repo); D2+ RAG.
[5] draft_banner_concept
Out:Concept {layout, copy{headline, subheadline, cta_text},
palette_usage, image_prompt, hierarchy_notes}
[6] generate_image
Vertex AI Imagen 4 — aspect_ratio="16:9", safety_filter_level="block_some". No
texto/logos/rostros en imagen.
[7] optimize_assets
Pillow + pillow-avif-plugin. Genera {webp{320,768,1280,1920}, avif{...},
fallback_jpg{1280}, alt_text_suggestion}. Weight cap <80KB @1280 WebP.
[8] render_html
Dual output: HTML standalone (preview/demo) + .liquid Shopify Section con bloques
conditional por customer.tags. Meta tags SEO + JSON-LD PromotionalOffer.
[9] audit
AuditReport {html_w3c, lighthouse{performance, lcp_ms, cls},
schema_valid, breakpoints_render, root_cause_hint?}. Max 2 retries upstream
según root_cause.


---

## Page 4

[10] human_review
Streamlit UI: preview iframe + AuditReport + acciones approve/reject/edit/schedule.
[11] schedule_or_publish
Branch immediate → nodo 12. Scheduled → INSERT supabase + pg_cron dispara nodo 12 al
target_time.
[12] publish_to_shopify
Admin API GraphQL themeFilesUpsert para .liquid + 4 assets WebP. Idempotent.
5. Brand Context Schema
Archivo brands/{brand_id}.md con frontmatter YAML siguiendo formato de Skill.
Reutilizable entre tiendas.
6. Personalización vía Shopify Sections + customer.tags
1---2 brand_id: avocado_store3 name: Avocado Store4 palette:5 primary:"#2E7D32"6 secondary:"#FFF8E1"7 accent:"#FF6F00"8 background:"#FFFFFF"9 text:"#212121"10 typography:11 heading:"Inter, sans-serif"12 body:"Inter, sans-serif"13 voice:14 tone:"warm, confident, no-bullshit"15 prohibited_words:["disruptive","revolutionary","synergy"]16 required_phrases:[]17 logo_url:"https://cdn.shopify.com/.../avocado-logo.svg"18 image_style_directives:"natural lighting, earthy palette, lifestyle photography, no peoplefaces, organic textures"19 shopify:20 store_domain:"avocado-dev.myshopify.com"21 theme_id:12345678922 default_placement:"homepage"23---24
1{% liquid2 assign default_variant = section.settings.default_variant3 assign chosen = default_variant4 if customer5 for tag in customer.tags6 case tag7 when 'vip'8 assign chosen = 'vip'9 when 'new_signup'10 assign chosen = 'new_signup'11 endcase12 endfor13 endif


---

## Page 5

7. Supabase — scheduling
8. Risk, HITL & Observability
Risk matrix (8 categorías)
14%}1516{% case chosen %}17 {% when 'vip' %}18 {%- render 'banner-block', variant: 'vip', section: section -%}19 {% when 'new_signup' %}20 {%- render 'banner-block', variant: 'new_signup', section: section -%}21 {% else %}22 {%- render 'banner-block', variant: 'default', section: section -%}23{% endcase %}24
1 CREATETABLE scheduled_banners (2 id uuid PRIMARYKEYDEFAULT gen_random_uuid(),3 brand_id textNOTNULL,4 payload jsonb NOTNULL,5 target_publish_at timestamptz NOTNULL,6 statustextDEFAULT'pending',7 created_at timestamptz DEFAULTnow()8);910 CREATETABLE audit_log (11 id bigserial PRIMARYKEY,12 trace_id text,13 brand_id text,14 event text,15 node text,16 payload jsonb,17 cost_usd numeric(10,4),18 created_at timestamptz DEFAULTnow()19);2021 SELECT cron.schedule('publish_due_banners','* * * * *', $$22 SELECT publish_due_banner_fn();23$$);24
Operacional Audit loop infinitoMedia Alto Max 2 retries,
escalate human
Comercial Banner mal-
aprobado en prod
Baja Alto HITL obligatorio,
sin override
CX Banner lento
daña LCP
Media Alto Lighthouse ≥ 90
gate, weight cap
Data Brand context
inválido
Baja Medio Pydantic
validation
Categoría Riesgo Prob. Impacto Control


---

## Page 6

HITL
Observability event plan
Cada nodo emite: event, node, trace_id, session_id, brand_id, timestamp,
duration_ms, cost_usd, audit_pass, review_decision, shopify_section_id.
Sinks: ADK trace → Cloud Logging + Supabase audit_log.
9. Success criteria
Técnico Shopify API rate
limit
Media Medio Backoff
exponencial 3×
Adopción Admin no
entiende UI
Media Medio UI mínima clara,
demo guion
Costo Imagen cost
runaway
Baja Bajo Cap diario
código, log
cost/banner
Legal Marca registrada
/ rostros en
imagen
Baja Alto Safety filter +
prompt directive
Punto único de HITL en nodo 10. Decisión humana: approve / reject / edit_request /
set_schedule. Sin bypass — la creatividad nunca pasa sola, aunque el audit pase.
Tiempo intake → publish < 10 min
Audit pass first-try ≥  70%
HITL approval first-try ≥  60%
Lighthouse Performance ≥  90 (100% banners publicados)
LCP 4G mobile < 1.0s
Schedule accuracy ±5 min
Brand context reusable ≥  2 tiendas demo
Personalización variantes ≥  3 variants demo
Métrica Target


---

## Page 7

10. MCP requirements
shopify-admin-mcp — Write-action (themeFilesUpsert, themeFilesGet, themeList). HITL
upstream cubre el riesgo. Escalar a aijolot-mcp-builder si no existe reusable en
Second Brain.
supabase — Cliente directo supabase-py en hackathon. MCP packaging es trabajo post-
hackathon.
11. Estructura de repo
12. Demo plan (D5)
1. Avocado Store — Black Friday immediate publish. Default variant. Cronómetro <10 min.
2. Avocado Store — Onboarding scheduled +2h. Variant new_signup. Valida pg_cron.
3. Demo Apparel — Product launch, 2 variants (vip + default). Brand context distinto. Valida
portabilidad.
13. Open Questions
14. Jira backlog
Epic  con 24 issues hijos:
1shopify-banner-agent/2 ├──  README.md3 ├──  pyproject.toml4 ├──  .env.example5 ├──  brands/6 │    ├──  avocado_store.md7 │    └──  demo_apparel.md8 ├──  agent/9 │    ├──  graph.py10 │    ├──  state.py11 │    ├──  nodes/ (12 nodos)12 │    ├──  prompts/13 │    ├──  tools/ (shopify, supabase, lighthouse, image_optimizer)14 │    └──  templates/ (banner_section.liquid.j2, banner_block.liquid.j2)15 ├──  ui/streamlit_review.py16 ├──  supabase/migrations/001_init.sql17 ├──  tests/18 └──  demo/scenarios.md19
Imagen 4 vs Gemini 2.5 Image — resolver D1 (Spike , Decision ).GH-2 GH-25
Lighthouse headless local del equipo (Chrome + node).
Streamlit auth para grabación demo pública.
MCP Shopify reusable en Second Brain — confirmar antes de build.
Cap diario de costo Imagen — definir umbral.
Licencia repo público — MIT default, confirmar.
GH-1
Tipo Issues


---

## Page 8

15. Definition of Done — Sprint
Spikes (D1) , , 
Stories D1 (infra) , , 
Stories D2 (nodos creativos) , , , , 
Stories D3 (render + audit) , , , 
Stories D4 (HITL + publish) , , 
Stories D5 (demo) , , , 
Meta  (Risks),  (Decision)
GH-2GH-3GH-4
GH-5GH-6GH-7
GH-8GH-9GH-10GH-11GH-12
GH-13GH-14GH-15GH-16
GH-17GH-18GH-19
GH-20GH-21GH-22GH-23
GH-24 GH-25
12 nodos del graph implementados, end-to-end funcional.
3 escenarios demo grabados.
README público con setup + demo gif + métricas reales.
Brand context schema documentado.
Repo público GitHub con LICENSE MIT.
AuditReport JSON adjunto por cada banner demo.
Submission al hackathon enviada.
Próximo paso: handoff a aijolot-value-sprint-execution una vez resueltos los
pre-requisitos D1 (acceso Vertex, dev store credentials, Supabase project + pg_cron,
decisión Imagen vs Gemini Image).
