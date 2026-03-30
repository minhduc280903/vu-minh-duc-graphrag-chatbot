"""
Retry Utilities
Implements exponential backoff for API calls as recommended by architect
"""
import asyncio
from typing import Callable, TypeVar, Any
from functools import wraps

from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

import logging

# Setup logging for tenacity
logging.basicConfig(level=logging.WARNING)
tenacity_logger = logging.getLogger("tenacity")


T = TypeVar('T')


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    max_delay: float = 60.0,
    multiplier: float = 5.0
):
    """
    Decorator for sync functions with exponential backoff
    
    Strategy (recommended by architect):
    - Retry 1: after 2s
    - Retry 2: after 10s  
    - Retry 3: after 60s (capped)
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=initial_delay, max=max_delay),
        before_sleep=before_sleep_log(tenacity_logger, logging.WARNING),
        reraise=True
    )


async def async_retry_with_backoff(
    func: Callable,
    *args,
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 5.0,
    **kwargs
) -> Any:
    """
    Async retry with exponential backoff
    
    Usage:
        result = await async_retry_with_backoff(
            send_message,
            user_id="123",
            text="Hello",
            max_attempts=3
        )
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
            
        except Exception as e:
            last_exception = e
            
            # Check if this is a non-retryable error (e.g., 400 policy violation)
            error_msg = str(e).lower()
            if any(term in error_msg for term in [
                "policy", "24 hour", "window closed", 
                "invalid", "permission", "blocked"
            ]):
                logger.error(f"❌ Non-retryable error: {e}")
                raise  # Don't retry policy violations
            
            if attempt < max_attempts:
                logger.warning(
                    f"⚠️ Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_multiplier, max_delay)
            else:
                logger.error(f"❌ All {max_attempts} attempts failed: {e}")
    
    raise last_exception


class APIRetryHandler:
    """
    Handler for API retries with notification support
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        notify_on_failure: bool = True
    ):
        self.max_attempts = max_attempts
        self.notify_on_failure = notify_on_failure
        self.failure_callbacks = []
    
    def add_failure_callback(self, callback: Callable):
        """Add callback to be called when all retries fail"""
        self.failure_callbacks.append(callback)
    
    async def execute(
        self, 
        func: Callable, 
        *args,
        context: str = "API call",
        **kwargs
    ) -> Any:
        """
        Execute function with retry and failure notification
        """
        try:
            return await async_retry_with_backoff(
                func,
                *args,
                max_attempts=self.max_attempts,
                **kwargs
            )
            
        except Exception as e:
            # Notify about failure
            if self.notify_on_failure:
                for callback in self.failure_callbacks:
                    try:
                        await callback(
                            context=context,
                            error=str(e),
                            args=args,
                            kwargs=kwargs
                        )
                    except Exception as cb_error:
                        logger.error(f"Failure callback error: {cb_error}")
            
            raise


# Global retry handler instance
api_retry_handler = APIRetryHandler(max_attempts=3, notify_on_failure=True)
