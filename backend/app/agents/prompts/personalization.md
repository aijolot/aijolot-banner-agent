# Personalization prompt (user-personalization skill)

Model: `gemini-3.5-flash` · Structured output: `Variants[]`

Given a `Campaign`, produce a list of `Variants` for personalization via `customer.tags`. Always include a `default` variant. Add up to 3 additional variants only if the campaign goal benefits from segmentation (e.g. VIP discount, new-signup welcome).

Each variant: `{customer_tag, intent_delta, copy_override?}`. `intent_delta` describes how the message shifts (e.g. "VIP gets early access + 60% vs 40%"). Use `copy_override` only when the headline/cta must change wording, not styling.

Do not exceed 4 variants total (1 default + 3 segments).
