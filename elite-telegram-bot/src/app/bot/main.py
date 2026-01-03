from aiogram import Bot, Dispatcher
from app.config import settings
from app.services.rate_limit import RateLimiter

bot = Bot(token=settings.BOT_TOKEN)
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
