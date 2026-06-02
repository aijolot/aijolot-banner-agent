# Prohibited Content Rules

Rules for scrubbing prohibited words and enforcing image prompt safety in the banner-concept-draft skill.

## Copy prohibited words

Source: `brand_context.voice.prohibited_words` (per-brand list).

**Scrubbing process:**
1. For each prohibited word, apply case-insensitive word-boundary regex: `\b{word}\b`
2. Replace with empty string
3. Clean up: collapse whitespace, strip leading/trailing punctuation (` -·—,:;`)
4. If scrubbing empties the entire field, fall back to generic text

**Example:**
- Brand prohibited: `["disruptive", "revolutionary", "synergy"]`
- Input: "Disruptive Black Friday synergy deals"
- Output: "Black Friday deals"

## Required phrases

Source: `brand_context.voice.required_phrases` (per-brand list).

**Insertion process:**
1. Take first required phrase from list
2. Check if already present in text (case-insensitive)
3. If not present and fits within char limit: append with ` · ` separator
4. If phrase alone exceeds limit: use phrase as entire field value (truncated)
5. Never force-insert if it breaks character limits

## Image prompt forbidden term substitutions

34-entry lookup table. Sorted by length (longest first) to prevent partial matches.

| Forbidden term | Safe replacement |
|---------------|-----------------|
| `text overlay` | `blank copy space` |
| `with text` | `with blank copy space` |
| `no text` | `blank copy space` |
| `no words` | `abstract details only` |
| `no letters` | `abstract details only` |
| `no signage` | `clean environmental areas` |
| `no captions` | `blank copy space` |
| `no caption` | `blank copy space` |
| `no headlines` | `blank hero focal area` |
| `no headline` | `blank hero focal area` |
| `no logos` | `mark-free brand-safe styling` |
| `no logo` | `mark-free brand-safe styling` |
| `no ui chrome` | `clean composition` |
| `no ui` | `clean composition` |
| `no faces` | `people-free scene` |
| `no face` | `people-free scene` |
| `typography` | `visual rhythm` |
| `words` | `abstract details` |
| `letters` | `abstract details` |
| `signage` | `clean environmental areas` |
| `captions` | `blank copy space` |
| `caption` | `blank copy space` |
| `headlines` | `blank hero focal area` |
| `headline` | `blank hero focal area` |
| `buttons` | `commerce-neutral shapes` |
| `button` | `commerce-neutral shape` |
| `modals` | `clean composition` |
| `modal` | `clean composition` |
| `screens` | `abstract display-free areas` |
| `screen` | `abstract display-free area` |
| `logos` | `mark-free brand-safe styling` |
| `logo` | `mark-free brand-safe styling` |
| `ui chrome` | `clean composition` |
| `ui` | `clean composition` |
| `faces` | `people-free scene` |
| `face` | `people-free scene` |
| `text` | `blank copy space` |

**Why positive substitutions?** Image models interpret negation ("no text") as a request TO include the negated concept. Always use positive descriptions of what SHOULD be in the image.

## Copy character limits

| Field | Max chars | Fallback if empty after scrub |
|-------|-----------|-------------------------------|
| `headline` | 58 | "Featured offer" |
| `subheadline` | 110 | (audience + tone description) |
| `cta` | 28 | "Shop now" |

## Palette token naming

`palette_usage` maps semantic roles to palette token names:

| Role | Source | Example |
|------|--------|---------|
| `background` | `palette[1].name` (secondary) | "Canvas" |
| `text` | `palette[0].name` (primary) | "Ink" |
| `cta_background` | `palette[2].name` (accent) | "Flame" |
| `cta_text` | `palette[1].name` (secondary) | "Canvas" |

Never use hex values (`#2E7D32`) — always use the `name` field from `PaletteColor`.
