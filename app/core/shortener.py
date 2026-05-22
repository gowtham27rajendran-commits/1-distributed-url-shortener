import string
import time
from typing import Optional

ALPHABET = string.ascii_letters + string.digits  # Base62
BASE = len(ALPHABET)
_counter = int(time.time() * 1000)


def encode_base62(num: int) -> str:
    """
    Convert integer to Base62 string.
    Design: counter-based > random — guarantees uniqueness without DB check.
    62^7 = 3.5 trillion combinations. Sufficient for any realistic scale.
    """
    if num == 0:
        return ALPHABET[0]
    result = []
    while num:
        result.append(ALPHABET[num % BASE])
        num //= BASE
    return ''.join(reversed(result))


def decode_base62(s: str) -> int:
    result = 0
    for char in s:
        result = result * BASE + ALPHABET.index(char)
    return result


def generate_short_code(custom_alias: Optional[str] = None) -> str:
    """
    In distributed system: replace _counter with Redis INCR.
    Redis INCR is atomic — no two workers will get the same counter value.
    """
    global _counter
    if custom_alias:
        return custom_alias[:10]
    _counter += 1
    return encode_base62(_counter)


class TokenBucketRateLimiter:
    """
    Token bucket > fixed window because it handles burst traffic gracefully.
    Fixed window: 100 reqs at 00:59 + 100 reqs at 01:00 = 200 in 2 seconds. Bad.
    Token bucket: burst allowed up to capacity, but average is enforced.

    Production: store bucket state in Redis for distributed workers.
    Key: ratelimit:{ip} → JSON{tokens, last_refill_ts}
    """
    def __init__(self, capacity: int = 100, refill_rate: float = 100 / 60):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens/second
        self._buckets: dict = {}

    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        if identifier not in self._buckets:
            self._buckets[identifier] = (self.capacity - 1, now)
            return True
        tokens, last = self._buckets[identifier]
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        if tokens >= 1:
            self._buckets[identifier] = (tokens - 1, now)
            return True
        return False


rate_limiter = TokenBucketRateLimiter()
