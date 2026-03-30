from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class DbSessionMiddleware(BaseMiddleware):
  def __init__(self, sessionmaker: async_sessionmaker[AsyncSession])
    self.sessionmaker = sessionmaker

  async def __call__(self, handler, event, data):
    async with self.sessionmaker() as session:
      data["session"] = session
      return await handler(event, data)
