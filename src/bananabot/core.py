"""BananaBot core with integrated Agent Loop, Provider, Session, and Message Bus."""

from __future__ import annotations

import importlib.util
import inspect
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

from bananabot.bus import MessageBus
from bananabot.providers import AnthropicProvider, ClaudeConfig
from bananabot.session import SessionManager

logger = logging.getLogger(__name__)


class Skill:
    """Base class for all bananabot skills."""

    name: str = ""
    description: str = ""

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


class AgentLoop:
    """Integrated agent loop with LLM, session, and message bus."""

    def __init__(
        self,
        provider: AnthropicProvider | None = None,
        session_manager: SessionManager | None = None,
        message_bus: MessageBus | None = None,
    ) -> None:
        self.skills: dict[str, Skill] = {}
        self.provider = provider or AnthropicProvider()
        self.sessions = session_manager or SessionManager()
        self.bus = message_bus or MessageBus()

    async def start(self) -> None:
        """Start message bus and load skills."""
        await self.bus.start()
        await self.load_builtin_skills()
        logger.info(f"AgentLoop started with {len(self.skills)} skills")

    async def stop(self) -> None:
        """Stop message bus and cleanup."""
        await self.bus.stop()
        await self.provider.close()
        logger.info("AgentLoop stopped")

    def register_skill(self, skill: Skill) -> None:
        if not skill.name:
            raise ValueError("Skill must define a non-empty name")
        self.skills[skill.name] = skill
        logger.debug(f"Registered skill: {skill.name}")

    def list_skills(self) -> list[Skill]:
        return [self.skills[name] for name in sorted(self.skills)]

    async def load_builtin_skills(self) -> None:
        await self.load_skills_from_dir(Path(__file__).parent / "skills")

    async def load_skills_from_dir(self, skills_dir: str | Path) -> None:
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"Skills directory not found: {skills_path}")
            return

        for module_path in sorted(skills_path.glob("*.py")):
            if module_path.name.startswith("__"):
                continue
            try:
                module = self._load_module(module_path)
                for skill_class in self._discover_skill_classes(module):
                    self.register_skill(skill_class())
            except Exception as e:
                logger.error(f"Failed to load skill from {module_path}: {e}")

    async def chat(
        self,
        session_id: str,
        user_message: str,
        system_prompt: str | None = None,
    ) -> str:
        """Process a chat message with session context."""
        # Get or create session
        session = self.sessions.get_or_create(session_id)

        # Add user message
        session.add_turn("user", user_message)

        # Build context
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(session.get_context())

        # Convert to provider format
        from bananabot.providers.anthropic import Message

        provider_messages = [
            Message(role=m["role"], content=m["content"]) for m in messages
        ]

        # Call LLM
        try:
            response = await self.provider.chat(provider_messages)
            content = response.get("content", [{}])[0].get("text", "")

            # Add assistant response to session
            session.add_turn("assistant", content)

            # Publish event
            await self.bus.publish(
                "chat.response",
                {"session_id": session_id, "response": content},
            )

            return content
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"❌ Error: {str(e)}"

    async def execute_skill(self, skill_name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a skill by name."""
        skill = self.skills.get(skill_name)
        if skill is None:
            return {"error": f"Skill '{skill_name}' not found"}

        logger.info(f"Executing skill: {skill_name}")
        result = await skill.execute(**kwargs)

        # Publish event
        await self.bus.publish(
            "skill.executed",
            {"skill": skill_name, "result": result},
        )

        return result

    @staticmethod
    def _load_module(module_path: Path) -> ModuleType:
        module_name = f"bananabot_dynamic_{module_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _discover_skill_classes(module: ModuleType) -> list[type[Skill]]:
        discovered: list[type[Skill]] = []
        for _, attr in inspect.getmembers(module, inspect.isclass):
            if not issubclass(attr, Skill) or attr is Skill:
                continue
            if attr.__module__ != module.__name__:
                continue
            discovered.append(attr)
        return discovered
