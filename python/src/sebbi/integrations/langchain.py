"""
LangChain / LangGraph: a receipt for every tool call (and, optionally, every model answer).

    from sebbi.integrations.langchain import SebbiCallbackHandler
    agent.invoke({"input": "..."}, config={"callbacks": [SebbiCallbackHandler()]})
"""
from typing import Any, Dict, Optional
from uuid import UUID

import sebbi

try:  # langchain-core is optional; the handler is duck-typed if it is absent
    from langchain_core.callbacks import BaseCallbackHandler as _Base  # type: ignore
except Exception:  # pragma: no cover
    _Base = object  # type: ignore


class SebbiCallbackHandler(_Base):  # type: ignore[misc]
    """Seals tool calls. Pass llm=True to also seal every model answer."""

    raise_error = False
    run_inline = True

    def __init__(self, llm: bool = False, prefix: str = "") -> None:
        if _Base is not object:
            super().__init__()
        self.llm = llm
        self.prefix = prefix
        self._open: Dict[str, Any] = {}

    def on_tool_start(self, serialized: Optional[Dict[str, Any]], input_str: str, *, run_id: UUID, **kw: Any) -> None:
        name = (serialized or {}).get("name") or kw.get("name") or "tool"
        self._open[str(run_id)] = (name, kw.get("inputs") or input_str)

    def on_tool_end(self, output: Any, *, run_id: UUID, **kw: Any) -> None:
        name, inp = self._open.pop(str(run_id), ("tool", None))
        sebbi.seal(inp, getattr(output, "content", output), self.prefix + name)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kw: Any) -> None:
        name, inp = self._open.pop(str(run_id), ("tool", None))
        sebbi.seal(inp, {"error_type": type(error).__name__}, self.prefix + name, "error")

    def on_llm_start(self, serialized: Optional[Dict[str, Any]], prompts: Any, *, run_id: UUID, **kw: Any) -> None:
        if self.llm:
            self._open[str(run_id)] = ("llm", prompts)

    def on_chat_model_start(self, serialized: Optional[Dict[str, Any]], messages: Any, *, run_id: UUID, **kw: Any) -> None:
        if self.llm:
            self._open[str(run_id)] = ("llm", messages)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kw: Any) -> None:
        if self.llm and str(run_id) in self._open:
            name, inp = self._open.pop(str(run_id))
            sebbi.seal(inp, response, self.prefix + name)
