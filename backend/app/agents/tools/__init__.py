"""ADK Tool wrappers — thin adapters over backend/app/services/*.

Tools follow the policy:
- Read-only tools have no HITL upstream requirement.
- Write-action tools (shopify_theme_upsert, scheduled_insert) MUST be invoked
  only after node 10 HITL approve. Coordinator enforces this contract.
"""
