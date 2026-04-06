"""BananaBot CLI with chat and bot modes."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from bananabot.channels import TelegramChannel, TelegramConfig
from bananabot.core import AgentLoop
from bananabot.providers import ClaudeConfig

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bananabot",
        description="🍌 BananaBot - Agent Loop with Skills",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-skills
    list_cmd = subparsers.add_parser("list-skills", help="List available skills")
    list_cmd.add_argument("--skills-dir", type=Path, default=None)

    # run skill
    run_cmd = subparsers.add_parser("run", help="Run a skill by name")
    run_cmd.add_argument("skill_name")
    run_cmd.add_argument("--skills-dir", type=Path, default=None)
    run_cmd.add_argument(
        "--arg", "-a",
        action="append",
        default=[],
        help="key=value arguments",
    )

    # chat (interactive)
    chat_cmd = subparsers.add_parser("chat", help="Interactive chat mode")
    chat_cmd.add_argument("--session", "-s", default="cli", help="Session ID")
    chat_cmd.add_argument("--system", default=None, help="System prompt")

    # telegram bot
    tg_cmd = subparsers.add_parser("telegram", help="Run Telegram bot")
    tg_cmd.add_argument("--token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Bot token")
    tg_cmd.add_argument("--webhook", default=os.getenv("TELEGRAM_WEBHOOK_URL"), help="Webhook URL")
    tg_cmd.add_argument("--allowed-users", help="Comma-separated user IDs")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    return asyncio.run(_run(args))


async def _run(args: argparse.Namespace) -> int:
    if args.command == "telegram":
        return await _run_telegram(args)

    # Initialize AgentLoop
    from bananabot.providers.anthropic import AnthropicProvider

    provider_config = ClaudeConfig(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    )

    loop = AgentLoop(
        provider=AnthropicProvider(provider_config),
    )
    await loop.start()

    try:
        skills_dir = getattr(args, "skills_dir", None)
        if skills_dir is None:
            await loop.load_builtin_skills()
        else:
            await loop.load_skills_from_dir(skills_dir)

        if args.command == "list-skills":
            skills = loop.list_skills()
            if not skills:
                print("No skills loaded.")
            else:
                print(f"\n{'Name':<20} {'Description'}")
                print("-" * 60)
                for skill in skills:
                    desc = skill.description or "No description"
                    print(f"{skill.name:<20} {desc[:40]}")
            return 0

        if args.command == "run":
            payload = _parse_args(args.arg)
            result = await loop.execute_skill(args.skill_name, **payload)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if "error" not in result else 1

        if args.command == "chat":
            return await _run_chat(loop, args)

    finally:
        await loop.stop()

    return 0


async def _run_chat(loop: AgentLoop, args: argparse.Namespace) -> int:
    """Interactive chat mode."""
    print(f"🍌 BananaBot Chat (session: {args.session})")
    print("Type 'exit' or 'quit' to exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                break
            if not user_input:
                continue

            response = await loop.chat(
                session_id=args.session,
                user_message=user_input,
                system_prompt=args.system,
            )
            print(f"\nBot: {response}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Chat error: {e}")
            print(f"❌ Error: {e}")

    return 0


async def _run_telegram(args: argparse.Namespace) -> int:
    """Run Telegram bot."""
    if not args.token:
        print("Error: Telegram bot token required. Set TELEGRAM_BOT_TOKEN env var or use --token")
        return 1

    allowed_users = []
    if args.allowed_users:
        allowed_users = [int(u.strip()) for u in args.allowed_users.split(",")]

    config = TelegramConfig(
        token=args.token,
        webhook_url=args.webhook,
        allowed_users=allowed_users,
    )

    # Initialize AgentLoop
    from bananabot.providers.anthropic import AnthropicProvider

    provider_config = ClaudeConfig(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    )

    loop = AgentLoop(
        provider=AnthropicProvider(provider_config),
    )
    await loop.start()
    await loop.load_builtin_skills()

    # Setup Telegram channel
    channel = TelegramChannel(config)

    @channel.on_message
    async def handle_message(session_id: str, user_id: str, text: str) -> str:
        return await loop.chat(
            session_id=session_id,
            user_message=text,
            system_prompt="You are BananaBot, a helpful AI assistant.",
        )

    try:
        await channel.start()
        print("🍌 BananaBot Telegram bot running...")
        print("Press Ctrl+C to stop")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await channel.stop()
        await loop.stop()

    return 0


def _parse_args(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Argument must be key=value, got: {item}")
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


if __name__ == "__main__":
    sys.exit(main())
