from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from app.db.models import URL
from app.cache.redis_client import cache_url, get_url, increment_click
from app.core.shortener import generate_short_code, rate_limiter

router = APIRouter()


class ShortenRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None


@router.post("/shorten")
async def shorten_url(req: ShortenRequest, request: Request):
    if not rate_limiter.is_allowed(request.client.host):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 100 req/min.")

    short_code = generate_short_code(req.custom_alias)
    await cache_url(short_code, str(req.url))

    return {
        "short_code": short_code,
        "short_url": f"{request.base_url}{short_code}",
        "original_url": str(req.url),
        "expires_at": req.expires_at,
    }


@router.get("/stats/{short_code}")
async def get_stats(short_code: str):
    url = await get_url(short_code)
    if not url:
        raise HTTPException(status_code=404, detail="Not found.")
    return {"short_code": short_code, "original_url": url}


@router.get("/{short_code}")
async def redirect_url(short_code: str, request: Request):
    # 1. Cache check (sub-millisecond)
    original_url = await get_url(short_code)

    if not original_url:
        raise HTTPException(status_code=404, detail="URL not found.")

    # Async analytics — never blocks the redirect
    await increment_click(short_code)

    # 302 not 301: browser won't cache it, so every click is tracked
    return RedirectResponse(url=original_url, status_code=302)
