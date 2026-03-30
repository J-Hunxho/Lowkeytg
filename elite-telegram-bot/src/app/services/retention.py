from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from ..models import AccessGrant, User, UserBadge, UserStreak


class RetentionService:
    def __init__(self, session):
        self.session = session

    async def touch_login(self, user: User) -> UserStreak:
        today = date.today()
        streak = await self.session.scalar(select(UserStreak).where(UserStreak.user_id == user.id))
        if streak is None:
            streak = UserStreak(user_id=user.id, current_streak=1, best_streak=1, last_seen_date=today, total_logins=1)
            self.session.add(streak)
            try:
                await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
                streak = await self.session.scalar(select(UserStreak).where(UserStreak.user_id == user.id))
                if streak is None:
                    raise

        if streak.last_seen_date == today:
            await self._sync_badges(user, streak)
            return streak
        else:
            if streak.last_seen_date == today - timedelta(days=1):
                streak.current_streak += 1
            else:
                streak.current_streak = 1
            streak.best_streak = max(streak.best_streak, streak.current_streak)
            streak.last_seen_date = today
            streak.total_logins += 1

        await self._sync_badges(user, streak)
        return streak

    async def _sync_badges(self, user: User, streak: UserStreak) -> None:
        if user.referral_count >= 5:
            await self._grant_badge(user.id, "referral_5", "Connector", "Referred 5+ members")
        if streak.current_streak >= 7:
            await self._grant_badge(user.id, "streak_7", "Consistent", "7-day login streak")
        founder_grant = await self.session.scalar(
            select(AccessGrant).where(
                AccessGrant.user_id == user.id,
                AccessGrant.sku == "founder_key",
                AccessGrant.active.is_(True),
            )
        )
        if founder_grant is not None:
            await self._grant_badge(user.id, "founder", "Founder", "Limited Founder Key holder")

    async def _grant_badge(self, user_id: int, badge_key: str, label: str, detail: str) -> None:
        existing = await self.session.scalar(select(UserBadge).where(UserBadge.user_id == user_id, UserBadge.badge_key == badge_key))
        if existing is not None:
            return
        badge = UserBadge(user_id=user_id, badge_key=badge_key, label=label, detail=detail)
        self.session.add(badge)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            pass

    async def badges_for_user(self, user: User) -> list[UserBadge]:
        rows = await self.session.execute(select(UserBadge).where(UserBadge.user_id == user.id).order_by(desc(UserBadge.granted_at)))
        return list(rows.scalars())

    async def referral_leaderboard(self, limit: int = 10) -> list[User]:
        rows = await self.session.execute(select(User).order_by(desc(User.referral_count), User.id.asc()).limit(limit))
        return list(rows.scalars())