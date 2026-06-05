# Art Concept Proposal — Taxonomy, Grounding & Iteration

Loaded on demand by the `art-direction` skill. Holds the concept taxonomy, the
product-rationale grounding rules, and the designer iteration protocol.

## 1. Shot types

| Shot | When to propose | Composition |
|------|-----------------|-------------|
| **hero** | Product is the star; brand/launch; clean premium look | Product-forward layout from KG `liquid_pattern`; AI background sets mood; copy block in the safe zone; no model |
| **usage** | Lifestyle / aspirational / segment-specific storytelling | Same product, a model treatment per segment; background contextualizes the scene; copy adapts to the variant audience |

The shot type is a proposal; the designer can flip it. For `usage`, the model
treatment is proposed per segment (see §3) and the SAME product/description is
held constant across angles for consistency.

## 2. Per-variant concept (1 campaign, N variants)

For each `personalization_variant` build one concept. Example for a citrus-summer
perfume campaign personalized by gender:

```
variant male (gender:male):
  shot_type: usage
  layout:    Hero split — product image column + copy column   [KG-RETRIEVED]
  product:   <featured product from catalog>                   [PROVIDER]
  model:     hombre — perfume presentado en un layout de outfit varonil,
             luz natural, sin rostro en foco                   [LLM-GENERATED]
  copy:      headline/subhead/cta para hombres jóvenes         [LLM-GENERATED]
  background:Limón Eléctrico (lima/cítrico)                    [LLM-GENERATED]
  rationale: ... evidence + tag

variant female (gender:female):
  shot_type: usage
  model:     mujer — modelo aplicándose el perfume frente al espejo,
             luciendo un atuendo veraniego                     [LLM-GENERATED]
  copy:      headline/subhead/cta para mujeres jóvenes         [LLM-GENERATED]
  background:Atardecer de Héroes (toronja/ámbar)               [LLM-GENERATED]
```

No variants in the brief → a single default concept (no invented split).

## 3. Model treatment proposals (usage)

Propose a treatment, not a real identity. Keep faces out of focus (image-safety).
Vary by segment; keep the product description identical across variants.

| Segment cue | Treatment proposal |
|-------------|--------------------|
| hombre / masculino | producto en un layout de outfit varonil; manos/torso; luz direccional |
| mujer / femenino | modelo aplicándose el producto frente al espejo; atuendo acorde; luz suave |
| unisex / editorial | composición editorial neutra, producto protagonista |
| VIP / lujo | set premium minimalista, materiales nobles |

All model treatments are `[LLM-GENERATED]` concepts; the eventual image is
generated via `art-prompt-propose` (usage) + `generate-art`. Add a consistency
caveat `[HYPOTHESIS]`: single-shot generation is not pixel-stable across angles.

## 4. Product selection & rationale (grounding rules)

The featured product comes ONLY from the catalog snapshot (`[PROVIDER]`). When
recommending one over another, the rationale MUST be grounded:

| Claim | Allowed tag | Required basis |
|-------|-------------|----------------|
| "más vendido / mayor stock rotation" | `[PROVIDER]` | catalog stock/sales fields |
| "históricamente mayor CTR en banners" | `[KG-RETRIEVED]` | a `prior_banner` doc with the metric |
| "creo que tendrá mayor CTR" | `[HYPOTHESIS]` | must add a validation note (A/B, measure) |
| any specific CTR/conversion % | only if from catalog/KG | NEVER fabricate a number |

If there is no evidence to rank products, present 2–3 options without a fabricated
ranking and ask the designer to choose (Recommend-Nothing on the ranking).

## 5. Designer iteration protocol

The agent proposes; the designer iterates. Map feedback to the single affected
step — do not regenerate the whole concept:

| Feedback intent | Re-run step | Skill |
|-----------------|-------------|-------|
| copy / tone / wording / discount emphasis | step 2 | banner-concept-draft (Gemini) |
| background / color / mood | step 3 | background-options-generate |
| different product / featured item | step 4 | catalog re-pick (no invention) |
| model / pose / scene (usage) | step 5 | art-prompt-propose (usage) + generate-art |
| layout / structure | step 1 | layout-retrieve |

Track concept state: `proposed → changes_requested → accepted`. Only an
`accepted` concept hands off to Assembly. Post-assembly edits are a different
skill (`banner-edit`).

## 6. Evidence → origin tag (quick map)

- Comes from the client/brief → `[USER-PROVIDED]`
- Comes from the Shopify catalog → `[PROVIDER]`
- Comes from a KG doc (layout/best_practice/prior_banner/brand_example) → `[KG-RETRIEVED]`
- Reasoned from the above → `[INFERENCE]` (cite the basis)
- A reasonable but unvalidated bet → `[HYPOTHESIS]` (add validation plan)
- Required but absent → `[MISSING]` (never fabricate)
