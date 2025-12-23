"""
Simple in-memory cache for analysis results
(Can be replaced with SQLite/Redis in production)
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

# In-memory cache
_cache: Dict[str, dict] = {}
_cache_lock = asyncio.Lock()

# Cache expiry (24 hours)
CACHE_EXPIRY = timedelta(hours=24)


async def save_analysis(analysis: dict) -> None:
    """Save analysis result to cache"""
    async with _cache_lock:
        analysis_id = analysis['analysis_id']
        _cache[analysis_id] = {
            **analysis,
            'cached_at': datetime.now()
        }


async def get_analysis(analysis_id: str) -> Optional[dict]:
    """Get analysis result from cache"""
    async with _cache_lock:
        result = _cache.get(analysis_id)
        if not result:
            return None

        # Check expiry
        cached_at = result.get('cached_at')
        if cached_at and datetime.now() - cached_at > CACHE_EXPIRY:
            # Expired, remove from cache
            del _cache[analysis_id]
            return None

        return result


async def clear_cache() -> None:
    """Clear all cached results"""
    async with _cache_lock:
        _cache.clear()


async def get_cache_stats() -> dict:
    """Get cache statistics"""
    async with _cache_lock:
        return {
            'total_entries': len(_cache),
            'entries': list(_cache.keys())
        }


# Singleton cache instance
def get_cache():
    """Get cache instance (for dependency injection)"""
    return {
        'save': save_analysis,
        'get': get_analysis,
        'clear': clear_cache,
        'stats': get_cache_stats
    }
