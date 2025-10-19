from __future__ import annotations

from collections import deque
from time import time
from typing import Deque, Dict, Optional

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore


class RateLimiter:
    def __init__(self, redis_client: Optional[Redis] = None) -> None:
        self.redis = redis_client
        self._memory_buckets: Dict[str, Deque[float]] = {}

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return False
        if self.redis:
            return await self._allow_redis(key, limit, window_seconds)
        return self._allow_memory(key, limit, window_seconds)

    async def allow_user(self, user_id: int, scope: str, limit: int, window_seconds: int) -> bool:
        key = f"user:{scope}:{user_id}"
        return await self.allow(key, limit, window_seconds)

    async def allow_global(self, scope: str, limit: int, window_seconds: int) -> bool:
        key = f"global:{scope}"
        return await self.allow(key, limit, window_seconds)

    async def _allow_redis(self, key: str, limit: int, window_seconds: int) -> bool:
        assert self.redis is not None
        now_ms = int(time() * 1000)
        window_ms = window_seconds * 1000
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, now_ms - window_ms)
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.zcard(key)
            pipe.expire(key, window_seconds * 2)
            removed, _, count, _ = await pipe.execute()  # type: ignore[misc]
        if count is None:
            return True
        if int(count) > limit:
            await self.redis.zrem(key, str(now_ms))
            return False
        return True

    def _allow_memory(self, key: str, limit: int, window_seconds: int) -> bool:
        bucket = self._memory_buckets.setdefault(key, deque())
        now = time()
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True
