# Campaign Brief — Field Extraction, Variants & Brief-Ready Validation

Reference loaded on demand by the `campaign-intake` (Campaign Brief) skill. Keeps
the SKILL.md body lean; this file holds the taxonomies and rules.

## 1. Natural-phrase → field map (ES + EN)

Extraction is preserve-filled: a match only *fills* an empty field or replaces a
non-empty value when the user clearly restates it. Never blank a field.

### urgency  (→ low | medium | high)
| Phrase (ES/EN) | Value |
|----------------|-------|
| "fin de semana", "este finde", "weekend", "flash", "hoy", "para mañana", "última hora", "urgente", "alta" | high |
| "esta semana", "this week", "pronto", "media", "medium" | medium |
| "sin apuro", "cuando se pueda", "siempre activo", "evergreen", "baja", "low" | low |

### audience  (free text; also seeds variants)
| Signal | Extraction |
|--------|-----------|
| "para mujeres jóvenes", "público femenino" | audience="mujeres jóvenes" (+ candidate variant `female`) |
| "para hombres", "público masculino" | audience="hombres" (+ candidate variant `male`) |
| "clientes VIP", "alto valor" | audience/variant `vip` |
| age phrases "18-30", "jóvenes" | fold into the audience string |

### cta  (action-first, ≤5 words)
"botón X", "que diga X", "call to action X" → cta = X. Default proposals (NOT
auto-filled): "Comprar ya", "Explora la colección", "Descubrir".

### placement
"hero", "home", "banner principal" → `hero_main`; "barra de anuncios" →
`announcement_bar`; "promo", "tarjeta" → `promo_card`; "colección" →
`collection_header`; "PDP", "página de producto" → `pdp_strip`. Keep the
human label; the placement skill maps to the canonical key.

### promo / discount  (→ campaign.promo_label)
Regex `(\d{1,3})\s*%` → "<n>% OFF". Phrases "X% de descuento", "rebaja", "oferta"
→ promo_label. If no number/percent stated → leave empty (do not invent).

### goal / tone / deadline
goal = the campaign objective sentence. tone = explicit adjectives or brand
voice. deadline = an ISO date if a concrete date/range is given, else null.

## 2. Personalization variants (1 campaign, N served by tag)

`personalization_dimension` names the customer field; `personalization_variants`
is one entry per value. Generation creates one `banner_variant` per entry.

```json
{
  "personalization_dimension": "gender",
  "personalization_variants": [
    {"key": "male",   "label": "Hombre", "audience": "hombres jóvenes 18-30", "customer_tag": "gender:male"},
    {"key": "female", "label": "Mujer",  "audience": "mujeres jóvenes 18-30", "customer_tag": "gender:female"}
  ]
}
```

### Common dimensions → variants (PROPOSALS — designer confirms)
| Dimension | key / label / customer_tag |
|-----------|----------------------------|
| gender | male·Hombre·`gender:male`; female·Mujer·`gender:female`; unisex·Unisex·`gender:unisex` |
| value tier | vip·Cliente VIP·`vip:true`; regular·Cliente·`vip:false` |
| lifecycle | new·Nuevo·`lifecycle:new`; returning·Recurrente·`lifecycle:returning` |
| none | single default audience, no variants |

Rules for proposing:
- Ground each variant's `audience` in the brief goal + KG segment evidence
  (`brand_example`/`prior_banner`) → tag `[KG-RETRIEVED]`; never invent a segment
  the store does not use.
- Propose variants only when the goal implies differentiated messaging. If not,
  recommend **no split** (single default) — this is the Recommend-Nothing path.
- `key` is a lowercase slug; `customer_tag` is `dimension:value` and must be
  unique across variants.

## 3. Brief-Ready gate — validation rules

The brief is **ready for Art** only when ALL pass:

1. Required non-empty: `goal`, `audience`, `cta`, `urgency`, `placement`.
2. `urgency ∈ {low, medium, high}`.
3. If `personalization_variants` non-empty: every entry has non-empty `key`,
   `label`, `audience`; all `customer_tag` distinct; `personalization_dimension`
   set.
4. If a promo was mentioned, `promo_label` parses to a non-empty string.
5. `deadline` is null or a valid ISO date.

On failure → emit ONE question for the single highest-priority offender, in this
order: goal → placement → audience → cta → urgency → variant coherence → promo.
Never advance to Art while any check fails. No bypass.

## 4. Origin tagging in the brief summary

Render each field with its tag, e.g.:
```
goal:      Promo de fin de semana de perfumes cítricos   [USER-PROVIDED]
audience:  mujeres jóvenes 18-30                          [USER-PROVIDED]
urgency:   high  (from "fin de semana")                   [LLM-GENERATED]
promo:     15% OFF                                        [USER-PROVIDED]
variants:  male, female                                   [KG-RETRIEVED] proposal — confirm
products:  212 Heroes EDP 80ml …                          [PROVIDER] catalog
cta:       (none yet)                                     [MISSING]
```
