from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..repos.referrals import ReferralRepository
from ..repos.users import UserRepository


class ReferralService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.referrals = ReferralRepository(session)

    async def process_referral(self, user: User, referral_code: Optional[str]) -> None:
        if not referral_code:
            return
        if user.referred_by_id:
            return
        referrer = await self.users.get_by_referral_code(referral_code)
        if not referrer or referrer.id == user.id:
            return
        await self.users.set_referred_by(user, referrer)
        await self.users.increment_referral_count(referrer)
        await self.referrals.create(referrer_id=referrer.id, referred_id=user.id)
