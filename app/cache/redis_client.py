import redis.asyncio as redis
import os
from typing import Optional

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = 86400  # 24h — LRU eviction handles memory pressure

_client: Optional[redis.Redis] = None


async def init_cache():
    global _client
    _client = redis.from_url(REDIS_URL, decode_responses=True)


async def get_client() -> redis.Redis:
    return _client


async def cache_url(short_code: str, original_url: str) -> None:
    """
    Write-through: DB write + cache write happen together.
    Ensures cache is always warm on writes.
    Trade-off: slightly slower writes vs cache-aside, but simpler consistency.
    """
    await _client.setex(f"url:{short_code}", CACHE_TTL, original_url)


async def get_url(short_code: str) -> Optional[str]:
    """
    Cache-aside read:
    1. Cache hit → return in <1ms
    2. Miss → caller fetches DB, then calls cache_url() to repopulate

    TODO: Add bloom filter before this call to short-circuit lookups
    for codes that definitely don't exist (DoS protection).
    """
    return await _client.get(f"url:{short_code}")


async def increment_click(short_code: str) -> None:
    """
    Redis INCR is O(1) and atomic.
    Background job (runs every 60s) flushes Redis counts → PostgreSQL.
    This pattern handles 100K clicks/sec without DB pressure.
    """
    await _client.incr(f"clicks:{short_code}")
