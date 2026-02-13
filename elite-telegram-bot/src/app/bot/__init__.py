"""Telegram bot package."""

from .main import bot, dispatcher, rate_limiter

__all__ = ["bot", "dispatcher", "rate_limiter"]
