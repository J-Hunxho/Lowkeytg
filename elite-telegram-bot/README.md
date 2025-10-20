# Elite Telegram Bot

Hunxho Codex engineered Telegram bot with FastAPI webhook surface, Stripe Checkout, and enterprise-grade observability. Built for Railway deployment, optimized for Python 3.11, aiogram 3, and modern best practices.

## Features

- ✅ **Command-rich bot**: `/start`, `/help`, `/profile`, `/ping`, `/about`, `/shop`, `/buy`, `/orders`, plus admin-only `/admin`, `/stats`, `/broadcast`, `/ban`, `/unban`.
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
4. Deploy. Railway executes `./start.sh`, which runs migrations (unless `SKIP_MIGRATIONS=1`) before booting Uvicorn. On startup the app sets the Telegram webhook if `SET_WEBHOOK_ON_START=true`.
5. Verify `/healthz`, then send a Telegram message to confirm the webhook handles updates.
6. Process a test Stripe payment to ensure fulfillment.

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
