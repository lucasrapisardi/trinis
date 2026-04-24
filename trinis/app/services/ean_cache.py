# PATH: /home/lumoura/trinis_ai/trinis/app/services/ean_cache.py
"""
EAN cache service using Redis.

Stores which EANs have already been synced per tenant+store,
along with their image hash. This allows the pipeline to:
  1. Skip AI enrichment for products whose description already exists
  2. Skip image upgrade for products whose source image hasn't changed

Cache TTL: 30 days (products are re-processed monthly with usage reset)
"""
import json
import redis
from app.core.config import get_settings

CACHE_TTL = 60 * 60 * 24 * 30  # 30 days


def _get_redis():
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _key(tenant_id: str, store_id: str, ean: str) -> str:
    return f"ean_cache:{tenant_id}:{store_id}:{ean}"


def get_cached(tenant_id: str, store_id: str, ean: str) -> dict | None:
    """
    Returns cached product data or None if not cached.
    Cached data includes: shopify_id, image_hash, enriched_description
    """
    try:
        r = _get_redis()
        data = r.get(_key(tenant_id, store_id, ean))
        r.close()
        return json.loads(data) if data else None
    except Exception:
        return None


def set_cached(tenant_id: str, store_id: str, ean: str, data: dict) -> None:
    """Cache product data after successful sync."""
    try:
        r = _get_redis()
        r.setex(_key(tenant_id, store_id, ean), CACHE_TTL, json.dumps(data))
        r.close()
    except Exception:
        pass


def invalidate(tenant_id: str, store_id: str, ean: str) -> None:
    """Invalidate cache for a specific product."""
    try:
        r = _get_redis()
        r.delete(_key(tenant_id, store_id, ean))
        r.close()
    except Exception:
        pass


def invalidate_all(tenant_id: str, store_id: str) -> int:
    """Invalidate all cached products for a tenant+store. Returns count deleted."""
    try:
        r = _get_redis()
        pattern = f"ean_cache:{tenant_id}:{store_id}:*"
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
        r.close()
        return len(keys)
    except Exception:
        return 0
