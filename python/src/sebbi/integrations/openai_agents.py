"""
OpenAI Agents SDK: a receipt for every tool call and every final answer.

    from sebbi.integrations.openai_agents import SebbiRunHooks
    result = await Runner.run(agent, "...", hooks=SebbiRunHooks())
"""
from typing import Any

import sebbi

try:
    from agents import RunHooks as _Base  # type: ignore
except Exception:  # pragma: no cover
    _Base = object  # type: ignore


class SebbiRunHooks(_Base):  # type: ignore[misc]
    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: Any) -> None:
        sebbi.seal({"agent": getattr(agent, "name", None), "tool": getattr(tool, "name", None)}, result,
                   "tool:" + str(getattr(tool, "name", "tool")))

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        sebbi.seal({"agent": getattr(agent, "name", None)}, output, "agent:" + str(getattr(agent, "name", "agent")))
