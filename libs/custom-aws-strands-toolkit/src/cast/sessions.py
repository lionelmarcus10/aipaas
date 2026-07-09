"""Session management — save, resume, list agent sessions."""

import os
from typing import Optional

from strands import Agent
from strands.session.file_session_manager import FileSessionManager
from strands.session.repository_session_manager import (
    Session,
    SessionAgent,
    SessionMessage,
)
from strands.types.session import SessionType


class SessionManager:
    """Wraps Strands FileSessionManager for save/resume/list.

    Args:
        storage_dir: Directory for session storage. Defaults to env
            STRANDS_SESSIONS_DIR or ./.strands_sessions.
    """

    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = storage_dir or os.environ.get(
            "STRANDS_SESSIONS_DIR",
            os.path.join(os.getcwd(), ".strands_sessions"),
        )

    def get_manager(self, session_id: str) -> FileSessionManager:
        os.makedirs(self.storage_dir, exist_ok=True)
        return FileSessionManager(session_id=session_id, storage_dir=self.storage_dir)

    def save(self, agent: Agent, session_id: str) -> str:
        """Save an agent's in-memory messages to disk."""
        sm = self.get_manager(session_id)
        try:
            sm.delete_session(session_id)
        except Exception:
            pass

        session = Session(session_id=session_id, session_type=SessionType.AGENT)
        sm.create_session(session)

        agent_id = agent.agent_id or "default"
        sm.create_agent(
            session_id,
            SessionAgent(
                agent_id=agent_id,
                state=agent.state or {},
                conversation_manager_state=agent.conversation_manager.get_state(),
            ),
        )

        for i, message in enumerate(agent.messages):
            sm.create_message(
                session_id,
                agent_id,
                SessionMessage(message=message, message_id=i),
            )

        return os.path.join(self.storage_dir, f"session_{session_id}")

    def list(self) -> list[str]:
        """List all saved session IDs."""
        if not os.path.isdir(self.storage_dir):
            return []
        return sorted(
            d for d in os.listdir(self.storage_dir)
            if os.path.isdir(os.path.join(self.storage_dir, d))
        )
