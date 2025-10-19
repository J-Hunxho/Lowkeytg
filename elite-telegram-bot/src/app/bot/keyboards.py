from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..config import settings


def shop_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    products = [
        ("Founder Key", "founder_key"),
        ("VIP Monthly", "vip_month"),
        ("VIP Annual", "vip_year"),
    ]
    for title, sku in products:
        buttons.append([
            InlineKeyboardButton(text=title, callback_data=f"buy:{sku}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def checkout_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Open Checkout", url=url)]]
    )


def referral_keyboard(referral_code: str) -> InlineKeyboardMarkup:
    link = f"https://t.me/{settings.telegram_bot_username}?start={referral_code}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Copy Referral Link", url=link)]]
    )
