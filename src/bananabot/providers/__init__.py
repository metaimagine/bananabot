"""Provider abstractions."""

from __future__ import annotations

from typing import Any, Protocol

from bananabot.providers.anthropic import AnthropicProvider, ClaudeConfig

__all__ = ["AnthropicProvider", "ClaudeConfig"]


class Provider(Protocol):
    """Abstract provider interface."""

    async def chat(self, messages: list[Any], tools: list[dict] | None = None) -> dict[str, Any]: ...
    async def close(self) -> None: ...
