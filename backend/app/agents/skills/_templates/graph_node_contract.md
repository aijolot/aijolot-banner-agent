# Graph-Node Skill Contract Template (AIjolot Banner Agent)

Adapted from the AIjolot Skill Contract Template for internal ADK graph-node
skills. These are NOT user-facing Skills — they are process contracts for nodes
in the 12-node banner-creation pipeline.

## Frontmatter (Anthropic Skills format)

Only `name` and `description` are routed by Claude. Internal metadata goes in
the body under "Node Metadata."

```yaml
---
name: <skill-id>
description: <one paragraph — what the node does, inputs, outputs>
---
```

## Required body sections (14)

```
# <Skill Display Name>
<One-line purpose.>

> **Node Metadata** | node: <N> | type: <deterministic|llm|retrieval|hybrid|provider-boundary|hitl> | model: <or none> | ticket: <GH-XX> | version: 0.2.0 | status: draft

## Node Invariants
2-4 principles that always hold regardless of input.

## Graph Entry Conditions
When the Coordinator invokes this node. BannerSessionState preconditions.
Retry re-entry path if applicable.

## Expected Inputs
State fields read + function parameters. Reference upstream skill_ids.

## Output Encoding
Pydantic model name, raw type (str, bytes). Language of text fields.
Character/size limits.

## Data Sources
Tools called, prompts loaded, sub-agents invoked, state fields consumed.
Table format preferred.

## Workflow
Numbered steps. Include gates if applicable.

## Output Contract
State fields written + return type. This is what downstream nodes consume.

## Data Provenance
Table mapping each output field to its provenance tag:
- [DETERMINISTIC] — computed from inputs, no randomness or LLM
- [LLM-GENERATED] — produced by a language model (specify which)
- [KG-RETRIEVED] — retrieved from the knowledge graph
- [PROVIDER] — returned by an external service
- [USER-PROVIDED] — pass-through from user input

## Pre/Post Conditions
Concrete Python-like assertions on BannerSessionState.

## Fallback Behavior
What happens when provider is unavailable, input is insufficient, or output
fails validation. Must be one of: deterministic default, retry (up to max),
escalate to HITL, or halt pipeline with error.

## Quality Criteria
Verifiable acceptance tests (checkbox format).

## Guardrails
Failure modes the node must avoid.

## Human Review Required
Write actions needing approval. "None. Automated node." for most nodes.

## References
Prompt files, tool files, sub-agents, related skill_ids — by name, not path.
```

## Line budget

Each SKILL.md must stay under 500 lines. Push detail to `references/` files
(one level deep only).

## Provenance tags

| Tag | Meaning | Example |
|-----|---------|---------|
| `[DETERMINISTIC]` | No LLM, no randomness | Parsed YAML brand context |
| `[LLM-GENERATED]` | Language model output | Campaign goal from Gemini Flash |
| `[KG-RETRIEVED]` | Knowledge graph retrieval | Best practice docs |
| `[PROVIDER]` | External service response | Image bytes from Nano Banana |
| `[USER-PROVIDED]` | Human input, unchanged | brand_id, HITL decision |
