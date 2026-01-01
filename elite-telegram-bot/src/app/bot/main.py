from __future__ import annotations

import os
from contextlib import asynccontextmanager
from http import HTTPStatus

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
PORT = int(os.getenv("PORT", "8080"))

# Telegram app
tg_app = Application.builder().token(TOKEN).build()

async def start_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is live ✅")

tg_app.add_handler(CommandHandler("start", start_cmd))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await tg_app.bot.set_webhook(f"{DOMAIN}/")
    await tg_app.initialize()
    await tg_app.start()
    yield
    await tg_app.stop()
    await tg_app.shutdown()

app = FastAPI(lifespan=lifespan)


@app.post("/")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)


@app.get("/")
def health():
    return {"status": "ok"}
