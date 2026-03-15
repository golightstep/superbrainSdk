"""
superbrain/integrations/langchain.py

LangChain Memory Adapter for SuperBrain
=========================================
Drop-in replacement for ConversationBufferMemory that stores conversation
history in SuperBrain's distributed RAM fabric instead of local memory.

This enables:
- Persistent conversation history across LLM restarts.
- Multiple chat sessions sharing the same conversational context.
- Sub-millisecond retrieval vs disk-based alternatives.

Usage::

    from superbrain.auto import AutoMemoryController
    from superbrain.integrations.langchain import SuperBrainMemory
    from langchain.chains import ConversationChain

    memory = AutoMemoryController()

    # Drop-in replacement for ConversationBufferMemory
    sb_memory = SuperBrainMemory(memory, session_id="user-123")

    chain = ConversationChain(
        llm=your_llm,
        memory=sb_memory,
        verbose=True
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("superbrain.langchain")

# Guard import so this module is importable even without LangChain installed.
try:
    from langchain.memory.chat_memory import BaseChatMemory
    from langchain.schema import BaseMessage, HumanMessage, AIMessage, messages_from_dict, messages_to_dict
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    # Stub base class for type checking
    BaseChatMemory = object  # type: ignore


class SuperBrainMemory(BaseChatMemory if _LANGCHAIN_AVAILABLE else object):  # type: ignore
    """
    A LangChain-compatible memory class that persists chat history to the
    SuperBrain distributed RAM fabric.

    When using this class many conversation agents on different machines
    can share the same session history with microsecond latency.
    """

    def __init__(
        self,
        controller: Any,   # AutoMemoryController
        session_id: str = "default",
        max_tokens: int = 4096,
        human_prefix: str = "Human",
        ai_prefix: str = "Assistant",
        memory_key: str = "history",
    ):
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain is not installed. Install it with: pip install langchain"
            )
        self._ctrl = controller
        self._session_id = session_id
        self._max_tokens = max_tokens
        self.human_prefix = human_prefix
        self.ai_prefix = ai_prefix
        self.memory_key = memory_key
        self._ctx = controller.context(f"langchain-session-{session_id}")
        self._ptr_key = "chat_history"
        self._messages_cache: List[BaseMessage] = []

        # Attempt to load existing history from the fabric
        self._load()

    # ---------- LangChain Memory Interface ----------

    @property
    def memory_variables(self) -> List[str]:
        return [self.memory_key]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, str]:
        """Return conversation history as a formatted string."""
        msgs = self._messages_cache
        buffer: List[str] = []
        for m in msgs:
            if isinstance(m, HumanMessage):
                buffer.append(f"{self.human_prefix}: {m.content}")
            else:
                buffer.append(f"{self.ai_prefix}: {m.content}")
        return {self.memory_key: "\n".join(buffer)}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Persist a new human/AI exchange to the distributed fabric."""
        human_msg = HumanMessage(content=inputs.get("input", ""))
        ai_msg = AIMessage(content=outputs.get("response", ""))
        self._messages_cache.extend([human_msg, ai_msg])
        # Trim to max_tokens (rough approximation: 4 chars ≈ 1 token)
        while sum(len(m.content) for m in self._messages_cache) > self._max_tokens * 4:
            self._messages_cache.pop(0)
        self._persist()

    def clear(self) -> None:
        """Clear conversation history from the fabric."""
        self._messages_cache = []
        self._persist()

    # ---------- Storage Helpers ----------

    def _persist(self) -> None:
        raw = json.dumps(messages_to_dict(self._messages_cache)).encode("utf-8")
        ptr_id = self._ctrl._client.allocate(max(len(raw), 4096))
        self._ctrl._client.write(ptr_id, 0, raw)
        # Store the ptr_id in the context's index
        self._ctx._store[self._ptr_key] = ptr_id
        logger.debug("[SuperBrainMemory] Persisted %d messages to ptr %s", len(self._messages_cache), ptr_id[:8])

    def _load(self) -> None:
        ptr_id = self._ctx._store.get(self._ptr_key)
        if ptr_id is None:
            return
        try:
            raw = self._ctrl._client.read(ptr_id, 0, 65536)
            data = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
            self._messages_cache = messages_from_dict(data)
            logger.info("[SuperBrainMemory] Loaded %d messages from fabric", len(self._messages_cache))
        except Exception as e:
            logger.warning("[SuperBrainMemory] Could not load history: %s", e)
