from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from ..config import settings


def shop_keyboard(products: list[dict[str, str]] | None = None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    products = products or []
    for product in products:
        buttons.append(
            [InlineKeyboardButton(text=product["title"], callback_data=f"buy:{product['sku']}")]
        )
    if settings.public_base_url or settings.railway_static_url or settings.railway_public_domain:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Open Mini App",
                    web_app=WebAppInfo(url=settings.mini_app_url),
                )
            ]
        )
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
