from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from ..logging import logger
from ..models import AccessGrant, AdminSetting, Product, Purchase, StripeEvent, StripeSubscription, SyncRun, User


class AdminService:
    def __init__(self, session):
        self.session = session

    async def settings_map(self) -> dict[str, Any]:
        rows = await self.session.execute(select(AdminSetting))
        return {row.key: row.value for row in rows.scalars()}

    async def upsert_setting(self, key: str, value: Any) -> None:
        row = await self.session.scalar(select(AdminSetting).where(AdminSetting.key == key))
        if row is None:
            row = AdminSetting(key=key, value=value)
            self.session.add(row)
        else:
            row.value = value

    async def dashboard(self) -> dict[str, Any]:
        products = list((await self.session.execute(select(Product).order_by(Product.sort_order.asc(), Product.id.asc()))).scalars())
        events = list((await self.session.execute(select(StripeEvent).order_by(desc(StripeEvent.id)).limit(25))).scalars())
        purchases = list((await self.session.execute(select(Purchase).order_by(desc(Purchase.id)).limit(25))).scalars())
        subs = list((await self.session.execute(select(StripeSubscription).order_by(desc(StripeSubscription.id)).limit(25))).scalars())
        runs = list((await self.session.execute(select(SyncRun).order_by(desc(SyncRun.id)).limit(25))).scalars())
        settings = await self.settings_map()
        return {
            "products": [
                {
                    "sku": p.sku,
                    "title": p.title,
                    "active": p.active,
                    "featured": p.featured,
                    "button_label": p.button_label,
                    "channel_announcement": p.channel_announcement,
                    "sort_order": p.sort_order,
                    "category": p.telegram_category,
                    "purchase_type": p.purchase_type,
                }
                for p in products
            ],
            "events": [{"event_id": e.event_id, "event_type": e.event_type, "processed_at": str(e.processed_at)} for e in events],
            "purchases": [{"id": p.id, "status": p.status, "sku": p.metadata_json.get("sku") if p.metadata_json else None, "amount_total": p.amount_total} for p in purchases],
            "subscriptions": [{"id": s.stripe_subscription_id, "status": s.status, "user_id": s.user_id} for s in subs],
            "sync_runs": [{"id": r.id, "source": r.source, "status": r.status, "detail": r.detail, "created_at": str(r.created_at)} for r in runs],
            "settings": settings,
        }

    async def set_product_overrides(self, sku: str, payload: dict[str, Any]) -> Product | None:
        product = await self.session.scalar(select(Product).where(Product.sku == sku))
        if product is None:
            return None

        if "featured" in payload:
            product.featured = bool(payload["featured"])
        if "active" in payload:
            product.active = bool(payload["active"])
        if "button_label" in payload:
            product.button_label = str(payload["button_label"]).strip()[:128] or None
        if "channel_announcement" in payload:
            product.channel_announcement = str(payload["channel_announcement"]).strip()[:2000] or None
        if "sort_order" in payload:
            try:
                product.sort_order = max(0, int(payload["sort_order"]))
            except (TypeError, ValueError):
                product.sort_order = 0
        if "telegram_category" in payload:
            product.telegram_category = str(payload["telegram_category"]).strip()[:128] or None
        if "title" in payload:
            title = str(payload["title"]).strip()
            if title:
                product.title = title[:255]
        if "description" in payload:
            product.description = str(payload["description"]).strip()[:5000] or None

        logger.info("admin.product_override_updated", sku=sku, keys=sorted(payload.keys()))
        return product

    async def set_admin_users(self, telegram_ids: list[int]) -> None:
        await self.upsert_setting("admin_user_ids", telegram_ids)
        result = await self.session.execute(select(User).where(User.telegram_id.in_(telegram_ids)))
        for user in result.scalars():
            user.is_admin = True

    async def manual_grant(self, user: User, sku: str, active: bool) -> None:
        grant = await self.session.scalar(select(AccessGrant).where(AccessGrant.user_id == user.id, AccessGrant.sku == sku))
        if grant is None:
            grant = AccessGrant(user_id=user.id, order_id=None, sku=sku, active=active)
            self.session.add(grant)
        else:
            grant.active = active

    async def record_sync_run(self, source: str, status: str, detail: str | None, triggered_by: int | None) -> None:
        self.session.add(SyncRun(source=source, status=status, detail=detail, triggered_by=triggered_by))
