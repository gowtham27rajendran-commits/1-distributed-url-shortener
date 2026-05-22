# Distributed URL Shortener

A production-grade URL shortening service built for horizontal scalability — handles 100K+ redirects/day with sub-10ms p99 latency.

## Architecture

```
Client → Load Balancer → FastAPI Workers (N instances)
                               ↓               ↓
                          Redis Cache      PostgreSQL
                               ↓
                          Kafka (async analytics)
```

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| ID generation | Base62 counter (not UUID) | Shorter URLs, zero collision without coordination |
| Cache strategy | Write-through, TTL=24h | Hot URLs always warm, no stale reads |
| Rate limiting | Token bucket | Handles burst traffic; fixed-window doesn't |
| Redirect type | HTTP 302 (not 301) | 301 is cached by browser — breaks analytics |
| Analytics writes | Redis → Kafka → DB | Decouples redirect latency from DB write speed |
| IP storage | SHA-256 hash only | GDPR compliance — never store raw IPs |

## Running Locally

```bash
docker-compose up -d
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /shorten | Create a short URL |
| GET | /{code} | Redirect to original URL |
| GET | /stats/{code} | Click analytics |

## What to implement next (your tasks)

- [ ] Consistent hashing for multi-node Redis (`app/cache/consistent_hash.py`)
- [ ] Bloom filter to skip DB lookup for nonexistent codes (DoS protection)
- [ ] Background job to flush Redis click counts → PostgreSQL
- [ ] Kafka consumer for full analytics events
- [ ] Load test with Locust (`tests/load_test.py`) targeting 1000 req/sec

## Interview Talking Points

**"Why Base62 over UUID?"**
UUIDs are 36 chars. Base62 gives you 7 chars for 3.5 trillion combinations — short enough to type, unique enough to never collide.

**"What happens if Redis goes down?"**
The redirect endpoint falls back to PostgreSQL. Latency spikes from <1ms to ~5ms but service stays up. We'd alert and spin up a new Redis node.

**"How do you handle a viral URL with 10K clicks/sec?"**
Redis INCR handles 100K ops/sec easily. DB is never touched per-click — a background job batches the count flush every 60 seconds.

**"How would you shard the DB at 1 billion URLs?"**
Hash(short_code) % N shards. Each shard is a separate PostgreSQL instance. The hash is deterministic so any worker knows which shard to query without a routing table.
