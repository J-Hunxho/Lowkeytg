from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Referral


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, referrer_id: int, referred_id: int) -> Referral:
        referral = Referral(referrer_id=referrer_id, referred_id=referred_id)
        self.session.add(referral)
        return referral
