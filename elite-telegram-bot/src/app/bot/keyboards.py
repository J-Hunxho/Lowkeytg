from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from ..config import settings


def _has_public_url() -> bool:
    return bool(settings.public_base_url or settings.railway_static_url or settings.railway_public_domain)


def shop_keyboard(products: list[dict[str, str]] | None = None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for product in products or []:
        buttons.append(
            [
                InlineKeyboardButton(text=product.get("button_label") or f"View {product['title']}", callback_data=f"product:view:{product['sku']}")
            ]
        )
    buttons.append([InlineKeyboardButton(text="🔄 Refresh Catalog", callback_data="catalog:refresh")])
    if _has_public_url():
        buttons.append([InlineKeyboardButton(text="🛍 Open Mini App", web_app=WebAppInfo(url=settings.mini_app_url))])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_detail_keyboard(sku: str, checkout_url: str | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if checkout_url:
        rows.append([InlineKeyboardButton(text="💳 Buy now", url=checkout_url)])
    else:
        rows.append([InlineKeyboardButton(text="💳 Buy now", callback_data=f"buy:{sku}")])
    rows.append([InlineKeyboardButton(text="⬅️ Back to catalog", callback_data="catalog:refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open Checkout", url=url)],
            [InlineKeyboardButton(text="Back to products", callback_data="catalog:refresh")],
        ]
    )


def referral_keyboard(referral_code: str) -> InlineKeyboardMarkup | None:
    username = settings.telegram_bot_username
    if not username:
        return InlineKeyboardMarkup(inline_keyboard=[])
    link = f"https://t.me/{username}?start={referral_code}"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Copy Referral Link", url=link)]]
    )