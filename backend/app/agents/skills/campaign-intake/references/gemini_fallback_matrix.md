# Gemini Fallback Decision Matrix

When to use Gemini vs deterministic extraction in the campaign-intake skill.

## Provider selection

| `AIJOLOT_INTAKE_PROVIDER` env | Provider used | Notes |
|-------------------------------|---------------|-------|
| `gemini` | Gemini 3.5 Flash | Requires `GOOGLE_API_KEY` |
| `""` (empty/unset) | Deterministic | Default for local dev, smoke tests |
| Any other value | Deterministic | Explicit non-Gemini selection |

## Gemini failure → fallback triggers

| Failure mode | Fallback reason logged | Recovery |
|-------------|----------------------|----------|
| API timeout (>30s) | `"Gemini timeout: {error}"` | Deterministic extraction on same message |
| API error (4xx/5xx) | `"Gemini API error: {status}"` | Deterministic extraction |
| Invalid response type | `"Gemini returned unexpected output type"` | Deterministic extraction |
| JSON parse failure | `"Gemini JSON decode error"` | Deterministic extraction |
| Network unreachable | `"Connection error: {error}"` | Deterministic extraction |

## Merge behavior (Gemini path)

When Gemini extracts fields from a turn, merge rules:
- New non-empty value overwrites empty field
- New non-empty value overwrites existing field (user update)
- Empty Gemini output for a field does NOT clear existing value
- Urgency is normalized through bilingual mapping before merge

## SSE streaming format

The API layer (`/api/v1/campaigns/intake`) wraps this skill in SSE:

```
data: {"type":"token","text":"..."}     # Streaming text chunks
data: {"type":"done","campaign":{...},"complete":true,"missing":[]}  # Final event
```

The skill itself returns `CampaignIntakeResult` — the SSE wrapping is done by the API router, not the skill.

## Urgency normalization table

| Input (case-insensitive) | Normalized output |
|--------------------------|-------------------|
| high, alta, urgent, urgente, asap, cuanto antes, ya, ya mismo | `high` |
| medium, media, soon, pronto | `medium` |
| low, baja, no rush, sin prisa, no hay prisa | `low` |
| (anything else) | `""` (empty — field not recognized) |
