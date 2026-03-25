# Elite Telegram Bot

Production-focused Telegram bot + FastAPI + Stripe + Mini App platform with admin controls and AI entitlements.

## What this project includes

- Telegram bot (aiogram) with webhook-first production runtime.
- FastAPI API surface for health, webhooks, checkout, catalog, admin, and AI endpoints.
- Stripe-backed catalog sync (products/prices from Stripe into DB).
- Checkout fulfillment into purchases, subscriptions, and access grants.
- Admin settings/dashboard endpoints for runtime control.
- Telegram Mini App marketplace + AI assistant panel.
- Alembic migrations for all core domain models.

---

## Local development

### Prerequisites

- Python 3.11
- `pip` or `uv`
- Stripe account + Telegram bot token

### Setup

```bash
cp .env.example .env
# Fill values (no secrets are committed to git)

pip install -r requirements.txt
PYTHONPATH=src alembic upgrade head
PYTHONPATH=src uvicorn app.web.api:app --reload --host 0.0.0.0 --port 8080
```

### Local verification

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/readyz
```

Expected:
- `healthz`: `{ "status": "ok" }`
- `readyz`: `status=ok` and checks for `database`, `telegram_config`, `stripe_config`, `ai_config`.

---

## Production deployment (Railway)

### Runtime model

- `railway.toml` starts: `/app/scripts/railway-start.sh`
- startup script:
  1. sets `PYTHONPATH`
  2. runs `alembic upgrade head` (unless disabled)
  3. launches uvicorn on `$PORT`

### Required Railway environment variables

#### Core
- `ENV=prod`
- `LOG_LEVEL=INFO`
- `DATABASE_URL=sqlite+aiosqlite:///./data.db` (or Postgres DSN)
- `RUN_MIGRATIONS_ON_START=true`

#### Public URL / webhook routing
- `PUBLIC_BASE_URL=https://<service>.up.railway.app`
- `SET_WEBHOOK_ON_START=true`
- `WEBHOOK_PATH=/webhook/telegram`

#### Telegram
- `TELEGRAM_ENABLED=true`
- `TELEGRAM_BOT_TOKEN=<botfather token>`
- `TELEGRAM_BOT_USERNAME=<bot username without @>`
- `TELEGRAM_WEBHOOK_SECRET_TOKEN=<strong secret>`
- `ADMIN_USER_IDS=<comma-separated telegram ids>`

#### Stripe
- `STRIPE_ENABLED=true`
- `STRIPE_SECRET_KEY=sk_live_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- (optional) `PRICE_ID_FOUNDER_KEY`, `PRICE_ID_VIP_MONTH`, `PRICE_ID_VIP_YEAR`

#### AI
- `AI_ENABLED=true`
- `AI_PROVIDER=openai` (or `echo` for non-production testing)
- `AI_DEFAULT_MODEL=gpt-4o-mini`
- `AI_OPENAI_API_KEY=<api key>`
- `AI_OPENAI_BASE_URL=https://api.openai.com/v1`
- `AI_OPENAI_TIMEOUT_SECONDS=30`

---

## Stripe webhook setup

Configure Stripe endpoint:
- URL: `https://<your-domain>/webhook/stripe`
- Events:
  - `product.created`
  - `product.updated`
  - `price.created`
  - `price.updated`
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`

Security:
- Signature validated from `Stripe-Signature` using `STRIPE_WEBHOOK_SECRET`.
- Event idempotency via persisted `stripe_events` event IDs.

---

## Telegram webhook setup

Endpoint:
- `POST /webhook/telegram` (or `WEBHOOK_PATH` override)

Security:
- `X-Telegram-Bot-Api-Secret-Token` validated with constant-time compare.
- Invalid secret returns `401`.
- Invalid payload returns `400`.

---

## Catalog and purchase flow

1. Sync Stripe catalog (`/api/admin/catalog/sync` or `/sync_products`).
2. Users browse via bot `/shop` or Mini App `/mini-app`.
3. Checkout session created via `/api/checkout`.
4. Stripe sends `checkout.session.completed`.
5. Order/purchase updated and `access_grants` activated.
6. Subscriptions update grants via subscription webhook events.

---

## Admin controls

- `GET /api/admin/dashboard`
- `GET /api/admin/settings`
- `PUT /api/admin/settings/{key}`
- `PATCH /api/admin/products/{sku}`
- `POST /api/admin/access`
- `POST /api/admin/catalog/sync`

All require `X-Admin-Telegram-Id` and admin authorization.

---

## AI service model

- `/ai` command in Telegram bot.
- `POST /api/ai/chat` for Mini App/API use.
- Tier resolution from active grants/subscriptions + configurable admin rules.
- Daily quota enforcement per tier.
- Request audit logs and daily usage counters persisted in DB.
- Provider abstraction supports swapping AI vendor without handler changes.

---

## Post-deploy verification checklist

1. `GET /healthz` returns 200.
2. `GET /readyz` returns `status=ok`.
3. `GET /health/webhook` shows Telegram webhook configured.
4. Trigger `/sync_products` as admin and verify `/api/catalog` returns items.
5. Run test checkout and confirm:
   - order marked paid,
   - purchase row created,
   - access grant activated.
6. Validate subscription webhook activates/deactivates grants correctly.
7. Validate `/api/admin/settings/{key}` updates runtime settings.
8. Validate `/ai` and `/api/ai/chat` enforce plan quota.
9. Validate Mini App loads catalog/account/AI data.

---

## Known operational risks

- SQLite is acceptable for small deployments; for scale, move to managed Postgres.
- If `AI_PROVIDER=openai` and key is missing, readiness degrades (`ai_config=invalid`).
- Webhook reliability depends on public HTTPS reachability and correct secrets.

