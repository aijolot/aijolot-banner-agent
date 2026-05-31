"""Agentic layer for the Shopify Banner Agent.

Layout:
- coordinator.py       Main ADK Agent orchestrating the 12-node graph.
- graph.py             Graph wiring (12 nodes, HITL at node 10).
- state.py             Pydantic state passed across nodes.
- sub_agents/          Specialist agents invoked on demand (CreativeDirector, Auditor).
- skills/              Process contracts (one folder per skill) consumed by nodes.
- tools/               Thin ADK Tool wrappers over backend/app/services/*.
- prompts/             Markdown prompt seeds shared across skills/sub_agents.
"""
