"""ADK-discoverable entry point for the Banner Coordinator agent.

`adk web --agents_dir backend/app/agents` will find this package and load
`root_agent` from `agent.py`.
"""

from .agent import root_agent

__all__ = ["root_agent"]
