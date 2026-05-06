"""
@ai-context: Memory module for tracking conversation turns and system context.
Manages short-term conversation history and current active state.
"""

import logging
from typing import TypedDict
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class MemoryContext(TypedDict):
    last_app: str
    last_action: str
    last_layer: str
    page: str

class MemoryTurn(BaseModel):
    role: str = Field(..., description="Role of the speaker (user or assistant)")
    content: str = Field(..., description="Text content of the turn")
    context: MemoryContext | None = Field(None, description="Context associated with this turn")

class MemoryManager:
    """Manages short-term memory and context for the agent."""
    def __init__(self, maxlen: int = 10) -> None:
        self.maxlen = maxlen
        self.history: list[MemoryTurn] = []
        self.context: MemoryContext = {
            "last_app": "",
            "last_action": "",
            "last_layer": "",
            "page": ""
        }
        logger.info("[MemoryManager] Initialized.")

    def add(self, role: str, content: str, context: MemoryContext | None = None) -> None:
        turn = MemoryTurn(role=role, content=content, context=context)
        self.history.append(turn)
        if len(self.history) > self.maxlen:
            self.history.pop(0)
        logger.info(f"[MemoryManager] Added turn for role '{role}'.")

    def update_context(self, key: str, value: str) -> None:
        if key == "last_app":
            self.context["last_app"] = value
        elif key == "last_action":
            self.context["last_action"] = value
        elif key == "last_layer":
            self.context["last_layer"] = value
        elif key == "page":
            self.context["page"] = value
        else:
            logger.warning(f"[MemoryManager] Invalid context key: '{key}'")
            return
        logger.info(f"[MemoryManager] Updated context '{key}' -> '{value}'")

    def get_context(self) -> MemoryContext:
        return self.context

    def build_llama_context(self) -> str:
        """Returns a string representation of the recent history for LLM prompt building."""
        lines = []
        for turn in self.history:
            lines.append(f"{turn.role.capitalize()}: {turn.content}")
        return "\n".join(lines)
