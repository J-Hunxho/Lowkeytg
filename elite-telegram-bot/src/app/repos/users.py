from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..utils.ids import generate_referral_code


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalars().first()

    async def get_by_referral_code(self, code: str) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.referral_code == code))
        return result.scalars().first()

    async def create_or_update(self, telegram_id: int, **kwargs: object) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)
        else:
            referral_code = await self._generate_unique_referral_code()
            user = User(telegram_id=telegram_id, referral_code=referral_code, **kwargs)
            self.session.add(user)
            await self.session.flush()
        return user

    async def list_user_ids(self) -> list[int]:
        result = await self.session.execute(select(User.telegram_id))
        return [row[0] for row in result.all()]

    async def set_referred_by(self, user: User, referrer: User) -> None:
        if user.id == referrer.id:
            return
        user.referred_by_id = referrer.id

    async def increment_referral_count(self, user: User) -> None:
        user.referral_count += 1

    async def _generate_unique_referral_code(self) -> str:
        while True:
            code = generate_referral_code()
            existing = await self.get_by_referral_code(code)
            if not existing:
                return code
