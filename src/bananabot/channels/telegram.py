"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )

    TG_AVAILABLE = True
except ImportError:
    TG_AVAILABLE = False

Handler = Callable[[str, str, str], Coroutine[Any, Any, str]]


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    token: str = Field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    webhook_url: str | None = Field(default_factory=lambda: os.getenv("TELEGRAM_WEBHOOK_URL"))
    webhook_port: int = 8443
    allowed_users: list[int] = Field(default_factory=list)


class TelegramChannel:
    """Telegram bot channel integration."""

    def __init__(self, config: TelegramConfig | None = None) -> None:
        if not TG_AVAILABLE:
            raise RuntimeError("python-telegram-bot not installed. Run: pip install python-telegram-bot")

        self.config = config or TelegramConfig()
        self.app: Application | None = None
        self._message_handler: Handler | None = None

    def on_message(self, handler: Handler) -> None:
        """Register message handler."""
        self._message_handler = handler

    async def start(self) -> None:
        """Start the bot."""
        if not self.config.token:
            raise ValueError("Telegram bot token not configured")

        self.app = Application.builder().token(self.config.token).build()

        # Register handlers
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        logger.info("Starting Telegram bot...")

        if self.config.webhook_url:
            await self.app.initialize()
            await self.app.bot.set_webhook(self.config.webhook_url)
            # Note: webhook server setup requires external ASGI/HTTP server
            logger.info(f"Webhook set to {self.config.webhook_url}")
        else:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()  # type: ignore
            logger.info("Telegram bot polling started")

    async def stop(self) -> None:
        """Stop the bot."""
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped")

    async def send_message(self, chat_id: int | str, text: str) -> None:
        """Send message to a chat."""
        if self.app and self.app.bot:
            await self.app.bot.send_message(chat_id=chat_id, text=text)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if update.effective_user and update.effective_message:
            user_id = update.effective_user.id
            if self.config.allowed_users and user_id not in self.config.allowed_users:
                await update.effective_message.reply_text("⛔ Access denied")
                return
            await update.effective_message.reply_text("🍌 BananaBot ready!")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if not update.effective_user or not update.effective_message:
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else user_id  # type: ignore

        # Check allowed users
        if self.config.allowed_users and user_id not in self.config.allowed_users:
            await update.effective_message.reply_text("⛔ Access denied")
            return

        text = update.effective_message.text or ""
        session_id = str(chat_id)

        logger.info(f"TG message from {user_id}: {text[:50]}...")

        if self._message_handler:
            try:
                response = await self._message_handler(session_id, str(user_id), text)
                await update.effective_message.reply_text(response)
            except Exception as e:
                logger.error(f"Handler error: {e}")
                await update.effective_message.reply_text(f"❌ Error: {str(e)[:200]}")
