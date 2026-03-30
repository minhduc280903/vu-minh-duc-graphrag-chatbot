"""
User Rate Limiter Service
Rate limiting per user ID (PSID) using Redis
"""
from typing import Optional
from datetime import datetime

from loguru import logger

from app.services.redis_client import redis_manager


class UserRateLimiter:
    """
    Rate limiter per user ID to prevent spam/abuse

    Unlike IP-based limiting, this tracks individual users
    since all FB/Zalo requests come from platform IPs.

    Features:
    - Configurable limits per time window
    - Auto-mute for excessive messaging
    - Admin notification for suspicious activity
    """

    def __init__(
        self,
        max_messages_per_minute: int = 10,
        max_messages_per_hour: int = 100,
        mute_duration_minutes: int = 5
    ):
        self.max_per_minute = max_messages_per_minute
        self.max_per_hour = max_messages_per_hour
        self.mute_duration = mute_duration_minutes

    async def check_rate_limit(self, user_id: str, page_id: str) -> dict:
        """
        Check if user is within rate limits

        Returns:
            dict with:
            - allowed: bool - whether the request should be processed
            - reason: str - reason if blocked
            - remaining: int - remaining requests in current window
            - reset_at: int - seconds until limit resets
        """
        if not redis_manager.client:
            # Redis not available, allow by default
            return {"allowed": True, "reason": None, "remaining": -1, "reset_at": 0}

        # Check if user is muted
        mute_key = f"muted:{page_id}:{user_id}"
        if await redis_manager.client.exists(mute_key):
            ttl = await redis_manager.client.ttl(mute_key)
            logger.warning(f"🔇 User {user_id} is muted for {ttl}s")
            return {
                "allowed": False,
                "reason": "rate_limited_muted",
                "remaining": 0,
                "reset_at": ttl
            }

        # Check minute limit
        minute_key = f"rate:min:{page_id}:{user_id}"
        minute_count = await redis_manager.client.incr(minute_key)

        if minute_count == 1:
            # First message this minute, set expiry
            await redis_manager.client.expire(minute_key, 60)

        minute_ttl = await redis_manager.client.ttl(minute_key)

        if minute_count > self.max_per_minute:
            # Rate limit exceeded - auto mute
            await self._mute_user(user_id, page_id)
            logger.warning(f"⚠️ User {user_id} exceeded minute limit ({minute_count}/{self.max_per_minute})")
            return {
                "allowed": False,
                "reason": "rate_limited_minute",
                "remaining": 0,
                "reset_at": minute_ttl
            }

        # Check hour limit
        hour_key = f"rate:hour:{page_id}:{user_id}"
        hour_count = await redis_manager.client.incr(hour_key)

        if hour_count == 1:
            await redis_manager.client.expire(hour_key, 3600)

        hour_ttl = await redis_manager.client.ttl(hour_key)

        if hour_count > self.max_per_hour:
            await self._mute_user(user_id, page_id)
            logger.warning(f"⚠️ User {user_id} exceeded hour limit ({hour_count}/{self.max_per_hour})")
            return {
                "allowed": False,
                "reason": "rate_limited_hour",
                "remaining": 0,
                "reset_at": hour_ttl
            }

        remaining = min(
            self.max_per_minute - minute_count,
            self.max_per_hour - hour_count
        )

        return {
            "allowed": True,
            "reason": None,
            "remaining": max(0, remaining),
            "reset_at": min(minute_ttl or 60, hour_ttl or 3600)
        }

    async def _mute_user(self, user_id: str, page_id: str):
        """Mute user for configured duration"""
        mute_key = f"muted:{page_id}:{user_id}"
        await redis_manager.client.setex(
            mute_key,
            self.mute_duration * 60,
            datetime.now().isoformat()
        )

        # Log suspicious activity
        logger.warning(f"🔇 User {user_id} muted for {self.mute_duration} minutes (spam protection)")

        # Optionally notify admin via Telegram
        try:
            from app.services.telegram_notifier import telegram_notifier
            from app.config import get_settings

            settings = get_settings()
            if settings.enable_telegram_notify:
                await telegram_notifier.send_message(
                    f"⚠️ <b>SPAM DETECTED</b>\n\n"
                    f"User ID: <code>{user_id}</code>\n"
                    f"Page: {page_id}\n"
                    f"Action: Muted for {self.mute_duration} minutes"
                )
        except Exception as e:
            logger.debug(f"Failed to notify about mute: {e}")

    async def unmute_user(self, user_id: str, page_id: str):
        """Manually unmute a user"""
        mute_key = f"muted:{page_id}:{user_id}"
        await redis_manager.client.delete(mute_key)
        logger.info(f"🔊 User {user_id} unmuted")

    async def get_user_stats(self, user_id: str, page_id: str) -> dict:
        """Get current rate limit stats for a user"""
        if not redis_manager.client:
            return {"minute_count": 0, "hour_count": 0, "is_muted": False}

        minute_key = f"rate:min:{page_id}:{user_id}"
        hour_key = f"rate:hour:{page_id}:{user_id}"
        mute_key = f"muted:{page_id}:{user_id}"

        minute_count = await redis_manager.client.get(minute_key)
        hour_count = await redis_manager.client.get(hour_key)
        is_muted = await redis_manager.client.exists(mute_key)

        return {
            "minute_count": int(minute_count or 0),
            "hour_count": int(hour_count or 0),
            "is_muted": bool(is_muted),
            "max_per_minute": self.max_per_minute,
            "max_per_hour": self.max_per_hour
        }


# Global instance with default limits
user_rate_limiter = UserRateLimiter(
    max_messages_per_minute=10,
    max_messages_per_hour=100,
    mute_duration_minutes=5
)
