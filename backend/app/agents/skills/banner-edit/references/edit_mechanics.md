# Banner Edit — Per-Target Edit Mechanics

Loaded on demand by `banner-edit`. Defines EXACTLY how each scoped edit is
applied to an assembled revision, what is preserved, and the revision bookkeeping.

## Principle: edit one layer, carry the rest

An assembled revision has four editable layers: **copy**, **background**, **image**,
**layout/concept**. Each edit mutates one layer and carries the others forward
unchanged into a NEW revision. The source revision is superseded, never modified.

```
source revision ──(scoped edit)──▶ new revision (selected)
        │                                  ▲
        └── superseded; recoverable ───────┘
```

## 1. Text / copy edit

**When:** "cambia el texto", "más urgente", "otro CTA", wording/tone/discount emphasis.

**How:**
1. Re-run copy generation ONLY: `banner-concept-draft` Gemini copy
   (`copy_for_audience` per variant) with the feedback folded into the prompt as
   a revision note. Deterministic fallback if no key.
2. Update each `banner_variant`'s `eyebrow/headline/subheadline/cta`.
3. Keep `concept.background`, `concept.generated_art` (image), layout **identical**.
4. Re-render HTML/Liquid with the new copy + the SAME background + image.

**Preserved:** background CSS, product image, layout. **Tag:** copy `[LLM-GENERATED]`.

## 2. Background HTML/CSS edit

**When:** "ajusta el fondo", "más cálido", "otro gradiente", "fondo más oscuro".

**How:**
1. Either (a) regenerate background options (`background-options-generate`, theme-
   aware) and take the new pick, or (b) apply the designer's explicit CSS tweak.
2. **Sanitize** the resulting CSS (strip `@import`, external `url()`,
   `expression(`, `javascript:`, `<script>`/`<iframe>`, inline `on*=`). Reject →
   fall back to a palette gradient.
3. Write `concept.background = {name, css, ...}` (scoped to `.aijolot-banner`).
4. Keep copy + image identical; re-render.

**Preserved:** copy, product image, layout. **Tag:** background `[LLM-GENERATED]` sanitized.

## 3. Product image edit — Nano Banana Pro

**When:** "regenera la imagen", "cambia el ángulo", "otro producto", "que se vea X".

**How:**
1. Build/refine the image prompt from the feedback + the current concept/product
   (`art-prompt-propose` for usage angles, or `image-prompt-refine`). Mark/text/
   face-free, brand-safe.
2. Generate with **Nano Banana Pro** (the real image provider / "pro" model) via
   the shared image seam (`image_gen.generate_image`), cost-gated; degrade to the
   free fake provider on no-key/cost-cap.
3. `image-asset-optimize` → upload via `asset_service` (asset_kind
   `product_image` for usage, `generated_background` for hero) → get public_url.
4. Swap the asset on the target `banner_variant` / `concept.generated_art`;
   keep copy + background identical; re-render with the new image.
5. If a product swap was requested, the new product comes from the catalog
   snapshot (`[PROVIDER]`) — never invented.

**Preserved:** copy, background, layout. **Tag:** image `[PROVIDER]` (Nano Banana Pro).
**Caveat:** single-shot generation is not pixel-stable across angles `[HYPOTHESIS]`.

## 4. Layout / concept edit (deeper)

**When:** "otro layout", "replantea el concepto", structural change.

**How:** hand back to `art-direction` to re-propose the concept (layout from KG +
copy + background) for the affected variant(s); the designer confirms before the
new revision is assembled. This is the only edit that may touch multiple layers,
and only because the designer asked for a structural rethink.

## Revision bookkeeping (all edits)

1. Create a new `campaign_revision` (status `draft` → `selected` on success),
   `generation_run_id` = the refinement run, `revision_number = max+1`.
2. Carry forward untouched layers verbatim from the source (copy/background/image).
3. Re-render `html_preview` + `liquid_config`; re-run audit → persist `audit_report`.
4. Supersede the previously selected revision; point the campaign at the new one.
5. Link the `refinement_request` (status `succeeded`/`failed`, result_revision_id).
6. Emit a diff summary: changed layer (tagged) vs preserved layers (`[UNCHANGED]`).

## Ambiguity → clarify (Recommend Nothing)

If `refinement-route` returns no confident target and the designer gave no
`target_nodes`, do NOT edit. Ask one question: "¿Edito el texto, el fondo o la
imagen?" Apply the edit only after the target is known.
