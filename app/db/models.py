from sqlalchemy import Column, String, Integer, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class URL(Base):
    """
    Sharding strategy: hash(short_code) % num_shards → even distribution.
    Range sharding rejected: hot short codes would overload one shard.

    click_count is denormalized here for O(1) reads on stats endpoint.
    Source of truth is click_events table; a background job syncs the count.
    """
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_code = Column(String(20), unique=True, nullable=False, index=True)
    original_url = Column(String(2048), nullable=False)
    user_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    click_count = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_user_created", "user_id", "created_at"),
        Index("ix_expires", "expires_at"),
    )


class ClickEvent(Base):
    """
    Append-only analytics table.
    Write path: redirect → Redis INCR (sync) → Kafka (async) → this table.
    Redirect latency is NEVER affected by analytics write speed.
    Partition by month when rows exceed 100M.
    """
    __tablename__ = "click_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    short_code = Column(String(20), nullable=False, index=True)
    clicked_at = Column(DateTime, default=datetime.utcnow)
    ip_hash = Column(String(64))     # SHA-256 of IP — never store raw (GDPR)
    country = Column(String(2))      # ISO 3166-1 alpha-2
    device_type = Column(String(20))
    referrer = Column(String(256), nullable=True)
