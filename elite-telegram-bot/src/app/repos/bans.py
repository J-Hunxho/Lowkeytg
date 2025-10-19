from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ban


class BanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: int) -> Optional[Ban]:
        result = await self.session.execute(select(Ban).where(Ban.user_id == user_id))
        return result.scalars().first()

    async def create_or_update(self, user_id: int, reason: Optional[str] = None) -> Ban:
        ban = await self.get_by_user_id(user_id)
        if ban is None:
            ban = Ban(user_id=user_id, reason=reason)
            self.session.add(ban)
        else:
            ban.reason = reason or ban.reason
        return ban

    async def remove(self, user_id: int) -> None:
        ban = await self.get_by_user_id(user_id)
        if ban:
            await self.session.delete(ban)
