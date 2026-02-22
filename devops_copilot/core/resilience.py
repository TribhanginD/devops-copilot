import asyncio
from functools import wraps
from typing import Callable, Any
from devops_copilot.utils.logger import logger

def retry_on_failure(retries: int = 3, backoff: float = 1.0):
    """Decorator for async retry logic with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait = backoff * (2 ** attempt)
                    logger.error(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
            raise last_exception
        return wrapper
    return decorator

class ResilienceLayer:
    """Handles fallback routing and global safety constraints."""
    
    @staticmethod
    async def with_fallback(primary_coro, fallback_coro):
        try:
            return await primary_coro
        except Exception as e:
            logger.warning(f"Primary path failed: {e}. Executing fallback...")
            return await fallback_coro
