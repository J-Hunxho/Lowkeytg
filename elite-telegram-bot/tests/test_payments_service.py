from __future__ import annotations

from types import SimpleNamespace

from app.services.payments import PaymentsService


def test_catalog_override_contains_premium_skus() -> None:
    service = PaymentsService(session=None)
    assert service._catalog_override("lowkey_entry")["title"] == "Lowkey Entry"
    assert service._catalog_override("founder_key")["button_label"] == "Claim Founder Key"


def test_serialize_catalog_product_applies_display_overrides() -> None:
    service = PaymentsService(session=None)
    product = SimpleNamespace(
        sku="lowkey_select",
        title="Stripe Product",
        description="",
        stripe_price_id="price_1",
        stripe_product_id="prod_1",
        currency="usd",
        unit_amount=9900,
        recurring_interval="month",
        featured=False,
        telegram_category=None,
        purchase_type="recurring",
        button_label=None,
        delivery_type="premium_commands",
        access_role="member:select",
        sort_order=0,
    )
    item = service._serialize_catalog_product(product)
    assert item["title"] == "Lowkey Select"
    assert item["featured"] is True
    assert item["button_label"] == "Join Select"
