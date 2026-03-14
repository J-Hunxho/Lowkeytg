# Elite Telegram Bot

Hunxho Codex engineered Telegram bot with FastAPI webhook surface, Stripe Checkout, and enterprise-grade observability. Built for Railway deployment, optimized for Python 3.11, aiogram 3, and modern best practices.

## Features

- ✅ **Command-rich bot**: `/start`, `/help`, `/profile`, `/ping`, `/about`, `/shop`, `/buy`, `/orders`, `/app`, plus admin-only `/admin`, `/stats`, `/broadcast`, `/ban`, `/unban`.
- ✅ **Command forwarding fallback** for unknown `/commands`, ensuring every command receives a bot response.
- ✅ **Telegram Mini App** served from `/mini-app` with WebApp integration (`sendData`) and launch button in `/app` + `/shop`.
- ✅ **Referral tracking** with automatic onboarding attribution and profile summaries.
- ✅ **Stripe Checkout** digital storefront with webhook fulfillment and idempotent order processing.
- ✅ **Rate limiting & anti-spam** with Redis-backed (or in-memory) throttling and abuse mitigation.
- ✅ **Internationalization scaffold** with MarkdownV2-safe messaging utilities.
- ✅ **FastAPI surface** providing health checks, Telegram & Stripe webhooks, and Stripe session creation.
- ✅ **SQLite + SQLAlchemy** storage with Alembic migrations and repository pattern.
- ✅ **Observability** via JSON logging, OpenTelemetry stubs, and error reporting hooks.
- ✅ **Production toolchain**: Dockerfile, Railway manifest, Makefile, Ruff, mypy, pytest, GitHub Actions CI, pre-commit.

## Architecture Overview

```
FastAPI (Uvicorn)
│
├── /healthz → status probe
├── /mini-app → Telegram Web App shell
├── /webhook/telegram → aiogram webhook dispatcher
├── /webhook/stripe → Stripe signature verification & fulfillment
└── /payments/checkout → Checkout Session API

aiogram Dispatcher → modular routers:
  • Base commands
  • Profile & referrals
  • Payments & shop
  • Admin & broadcast

Persistence → SQLAlchemy 2.x async ORM backed by SQLite (Railway volume)
Optional Redis → rate limiting + task queues
Stripe Service → Checkout sessions, webhook idempotency
Observability → Structured logging, OpenTelemetry stubs, pluggable error reporter
```

## Quickstart (Local)

### 1. Prerequisites

- Python 3.11 (see `.python-version`)
- [uv](https://github.com/astral-sh/uv) or `pip` for dependency management
- Optional: Redis for production-grade rate limiting

### 2. Clone & Configure

```bash
git clone https://github.com/your-org/elite-telegram-bot.git
cd elite-telegram-bot
cp .env.example .env
# fill in secrets: Telegram token, Stripe keys, etc.
```

### 3. Install Dependencies

```bash
make install
```

### 4. Run Database Migrations

```bash
make migrate
```

### 5. Launch Dev Server

```bash
make run
```

The FastAPI app listens on `http://127.0.0.1:8000`. `/healthz` should return `{ "status": "ok" }`.

### 6. Expose Webhook (Dev)

Use [ngrok](https://ngrok.com/) or [Cloudflare Tunnel](https://www.cloudflare.com/products/tunnel/) to expose your dev server:

```bash
ngrok http 8000
```

Set `PUBLIC_BASE_URL` to the tunnel URL and trigger the webhook update:

```bash
make webhook\:set
```

## Stripe Setup

1. Create products & prices in Stripe Dashboard.
2. Set the price IDs in `.env` (`PRICE_ID_FOUNDER_KEY`, etc.).
3. For local development, use `stripe listen --forward-to localhost:8000/webhook/stripe` and set `STRIPE_WEBHOOK_SECRET`.
4. Use `/shop` in Telegram to open the storefront, `/buy <sku>` to trigger Checkout.

## Railway Deployment

1. Create a new Railway project and select “Deploy from GitHub”.
2. Add all environment variables from `.env.example`.
3. Railway auto-assigns a public domain; set `PUBLIC_BASE_URL` to `https://<project>.up.railway.app` (or custom domain).
4. Deploy. Railway now runs `/app/scripts/railway-start.sh` from `railway.toml`.
5. Startup script behavior:
   - exports `PYTHONPATH=/app/src`
   - runs `alembic upgrade head` by default (`RUN_MIGRATIONS_ON_START=true`)
   - starts Uvicorn on `$PORT`.
6. Optional: set `RUN_MIGRATIONS_ON_START=false` if migrations are handled in a separate release job.
7. On startup the app sets the Telegram webhook if `SET_WEBHOOK_ON_START=true`.
8. Verify `/healthz`, then send a Telegram message to confirm the webhook handles updates.
9. Process a test Stripe payment to ensure fulfillment.


### Railway Environment Settings

Set these variables in Railway **before first deploy**:

| Variable | Required | Example | Notes |
|---|---|---|---|
| `ENV` | ✅ | `prod` | Runtime mode. |
| `LOG_LEVEL` | ✅ | `INFO` | Logging verbosity. |
| `DATABASE_URL` | ✅ | `sqlite+aiosqlite:///./data.db` | Use Postgres in production SaaS scale. |
| `RUN_MIGRATIONS_ON_START` | ✅ | `true` | Auto-runs `alembic upgrade head`. |
| `TELEGRAM_ENABLED` | ✅ | `true` / `false` | Master switch for Telegram runtime. |
| `TELEGRAM_BOT_TOKEN` | ✅ if Telegram enabled | `123456:ABC...` | Must be real BotFather token. |
| `TELEGRAM_BOT_USERNAME` | ✅ if Telegram enabled | `lowkeytg_bot` | Bot username without `@`. |
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | ✅ if Telegram enabled | `super-secret-value` | Header validation secret for Telegram webhook. |
| `PUBLIC_BASE_URL` | ✅ if Telegram enabled | `https://<service>.up.railway.app` | Used for webhook + mini app links. |
| `SET_WEBHOOK_ON_START` | ✅ | `true` | Auto-register webhook on startup. |
| `STRIPE_ENABLED` | Optional | `true` / `false` | Enable Stripe checkout path. |
| `STRIPE_SECRET_KEY` | ✅ if Stripe enabled | `sk_live_...` | Stripe API key. |
| `STRIPE_WEBHOOK_SECRET` | ✅ if Stripe enabled | `whsec_...` | Stripe signature verification key. |
| `PRICE_ID_FOUNDER_KEY` | Optional | `price_...` | SKU mapping. |
| `PRICE_ID_VIP_MONTH` | Optional | `price_...` | SKU mapping. |
| `PRICE_ID_VIP_YEAR` | Optional | `price_...` | SKU mapping. |
| `ADMIN_USER_IDS` | Optional | `12345,67890` | Comma-separated Telegram IDs. |
| `REDIS_URL` | Optional | `redis://...` | Improves distributed rate limits. |

## Tooling

- `make lint` → Ruff lint + format check
- `make type` → mypy (strict typed)
- `make test` → pytest suite
- `make webhook:set` / `make webhook:delete` → Manage Telegram webhook
- `make migrate` → Run Alembic upgrades

## Observability & Ops

- Structured JSON logs with request & user IDs; integrates with your log aggregator.
- Hooks for OpenTelemetry and Sentry-like error reporting.
- Idempotent Stripe webhook handling prevents double fulfillment.
- Rate limiting defends against abuse while providing telemetry.

## Contributing

- Run `pre-commit install` after clone.
- Ensure CI (`.github/workflows/ci.yml`) passes before push.

## License

MIT License © Hunxho Codex Engineering.
