"""Session management with turn-based memory compression."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Turn:
    """A single conversation turn."""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressedBlock:
    """Compressed representation of multiple turns."""

    summary: str
    start_turn: int
    end_turn: int
    timestamp: float


class Session:
    """Conversation session with automatic turn compression."""

    def __init__(
        self,
        session_id: str,
        max_turns: int = 20,
        compress_threshold: int = 10,
        compression_ratio: float = 0.3,
    ) -> None:
        self.session_id = session_id
        self.max_turns = max_turns
        self.compress_threshold = compress_threshold
        self.compression_ratio = compression_ratio

        self.turns: list[Turn] = []
        self.compressed: list[CompressedBlock] = []
        self.metadata: dict[str, Any] = {}

    def add_turn(self, role: str, content: str, **meta: Any) -> None:
        """Add a new turn to the session."""
        turn = Turn(role=role, content=content, metadata=meta)
        self.turns.append(turn)
        logger.debug(f"Session {self.session_id}: added {role} turn, total={len(self.turns)}")

        # Auto-compress if threshold reached
        if len(self.turns) >= self.compress_threshold:
            self._compress_old_turns()

    def _compress_old_turns(self) -> None:
        """Compress old turns into summary block."""
        # Keep last 4 turns uncompressed, compress the rest
        compress_count = len(self.turns) - 4
        if compress_count < 4:  # Need at least 4 turns to compress
            return

        turns_to_compress = self.turns[:compress_count]
        self.turns = self.turns[compress_count:]

        # Simple compression: extract key points (in real impl, use LLM)
        user_msgs = [t.content[:50] for t in turns_to_compress if t.role == "user"]
        summary = f"Previous context: discussed {len(user_msgs)} topics including: {', '.join(user_msgs[:3])}..."

        block = CompressedBlock(
            summary=summary,
            start_turn=len(self.compressed) * self.compress_threshold,
            end_turn=len(self.compressed) * self.compress_threshold + compress_count,
            timestamp=time.time(),
        )
        self.compressed.append(block)
        logger.info(f"Session {self.session_id}: compressed {compress_count} turns")

    def get_context(self, include_compressed: bool = True) -> list[dict[str, str]]:
        """Get conversation context for LLM."""
        context: list[dict[str, str]] = []

        # Add compressed summaries as system context
        if include_compressed and self.compressed:
            summaries = "\n".join([c.summary for c in self.compressed])
            context.append({"role": "system", "content": f"[Previous context]\n{summaries}"})

        # Add recent turns
        for turn in self.turns:
            context.append({"role": turn.role, "content": turn.content})

        return context

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict."""
        return {
            "session_id": self.session_id,
            "turns": [
                {"role": t.role, "content": t.content, "timestamp": t.timestamp}
                for t in self.turns
            ],
            "compressed": [
                {"summary": c.summary, "start": c.start_turn, "end": c.end_turn}
                for c in self.compressed
            ],
            "metadata": self.metadata,
        }


class SessionManager:
    """Manage multiple sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str, **kwargs: Any) -> Session:
        """Get existing session or create new."""
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id, **kwargs)
            logger.info(f"Created new session: {session_id}")
        return self._sessions[session_id]

    def get(self, session_id: str) -> Session | None:
        """Get session if exists."""
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
