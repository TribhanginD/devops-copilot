"""
base.py — Base Agent + Session State
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from devops_copilot.utils.logger import logger


class AgentState(BaseModel):
    """Represents the state of an agent during a session."""
    session_id: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    @abstractmethod
    async def chat(self, message: Any, state: AgentState) -> Any:
        """Process a message and return a response."""
        ...

    def _log_interaction(self, state: AgentState, role: str, content: str):
        preview = content[:120] if len(content) > 120 else content
        state.history.append({"role": role, "content": content})
        logger.info(f"[{self.name}] {role}: {preview}")
