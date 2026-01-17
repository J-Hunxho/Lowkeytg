from aiogram import Bot, Dispatcher
from app.config import settings
from app.services.rate_limit import RateLimiter

token = settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else None
if not token:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
bot = Bot(token=token)
dispatcher = Dispatcher()
rate_limiter = RateLimiter()

import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/healthz")
def health():
    return {"/healthz": "ok"}
