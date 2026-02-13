"""
Base Agent classes - the core abstraction for all pluggable agents.

Every specialized agent (GIPA, Dossier, Strategy, etc.) extends BaseAgent
and implements handle() + get_status(). This makes agents pluggable:
clients can pick which agents they want and register them.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class AgentContext:
    """Context passed to every agent handler."""

    user_id: str = "default"
    session_id: str = "default"
    conversation_history: Optional[List[Dict]] = None
    base_url: str = "http://localhost:8000"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Standard response from any agent."""

    message: str
    status: str = "completed"  # completed, collecting, ready, error
    agent_name: str = ""
    intent: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": "final_result",
            "message": self.message,
            "agent": self.agent_name,
            "status": self.status,
            "intent": self.intent,
            "data": self.data,
        }


class BaseAgent(ABC):
    """
    Abstract base for all pluggable agents.

    Subclasses must implement:
        - handle(): process a user message
        - get_status(): check session status

    Subclasses should set:
        - name: unique identifier (e.g. "gipa")
        - description: human-readable description
        - keywords: list of regex patterns for routing
        - active_statuses: session statuses that mean "route to me"
    """

    name: str = ""
    description: str = ""
    keywords: List[str] = []
    active_statuses: List[str] = []

    @abstractmethod
    async def handle(self, message: str, context: AgentContext) -> AgentResponse:
        """
        Process a user message.

        Args:
            message: The user's message
            context: AgentContext with user_id, session_id, history, etc.

        Returns:
            AgentResponse with the result
        """
        ...

    @abstractmethod
    async def get_status(self, session_id: str = "default", base_url: str = "http://localhost:8000") -> str:
        """
        Check the current session status.

        Returns:
            Status string (e.g. "none", "collecting", "ready", "generated")
        """
        ...

    def matches_keywords(self, message: str) -> bool:
        """Check if a message matches this agent's keywords."""
        if not self.keywords:
            return False
        pattern = r"\b(" + "|".join(self.keywords) + r")\b"
        return bool(re.search(pattern, message, re.IGNORECASE))

    def is_active_session(self, status: str) -> bool:
        """Check if the given status means this agent has an active session."""
        return status in self.active_statuses

    def get_tools(self) -> list:
        """
        Return LangChain tools this agent exposes to the ReAct agent.
        Override in subclass if the agent provides tools.

        Returns:
            List of LangChain tool functions
        """
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
