"""
Redis Client for State Management
Handles debouncing, admin handover state, and session data
"""
import json
from typing import Optional, Any

import redis.asyncio as redis
from loguru import logger


class RedisManager:
    """Async Redis connection manager"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
    
    async def connect(self, host: str, port: int, password: str = ""):
        """Initialize Redis connection"""
        self.client = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            decode_responses=True
        )
        # Test connection
        await self.client.ping()
        logger.info(f"Redis connected to {host}:{port}")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    # ============ Debounce Methods ============
    
    async def add_message_to_buffer(
        self, 
        user_id: str, 
        message: dict,
        debounce_seconds: int = 7
    ) -> list[dict]:
        """
        Add message to debounce buffer
        Returns all buffered messages for this user
        """
        key = f"debounce:{user_id}"
        
        # Add message to list
        await self.client.rpush(key, json.dumps(message))

        # Reset expiration (sliding window) - add 5s buffer for timing safety
        await self.client.expire(key, debounce_seconds + 5)
        
        # Get all messages
        messages = await self.client.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]
    
    async def get_and_clear_buffer(self, user_id: str) -> list[dict]:
        """Get all buffered messages and clear the buffer"""
        key = f"debounce:{user_id}"
        
        # Get all messages
        messages = await self.client.lrange(key, 0, -1)
        
        # Clear buffer
        await self.client.delete(key)
        
        return [json.loads(m) for m in messages]
    
    async def has_pending_messages(self, user_id: str) -> bool:
        """Check if user has pending messages in buffer"""
        key = f"debounce:{user_id}"
        return await self.client.exists(key) > 0
    
    # ============ Admin Handover Methods ============
    
    async def set_admin_handover(
        self, 
        page_id: str, 
        user_id: str, 
        minutes: int = 30
    ):
        """Mark conversation as taken over by admin"""
        key = f"admin_handover:{page_id}:{user_id}"
        await self.client.setex(key, minutes * 60, "1")
        logger.info(f"Admin handover set for {user_id} ({minutes} minutes)")
    
    async def is_admin_active(self, page_id: str, user_id: str) -> bool:
        """Check if admin is currently handling this conversation"""
        key = f"admin_handover:{page_id}:{user_id}"
        return await self.client.exists(key) > 0
    
    async def clear_admin_handover(self, page_id: str, user_id: str):
        """Clear admin handover flag"""
        key = f"admin_handover:{page_id}:{user_id}"
        await self.client.delete(key)
    
    # ============ Session Methods ============
    
    async def set_session_data(
        self, 
        user_id: str, 
        data: dict, 
        ttl: int = 3600
    ):
        """Store session data for user"""
        key = f"session:{user_id}"
        await self.client.setex(key, ttl, json.dumps(data))
    
    async def get_session_data(self, user_id: str) -> Optional[dict]:
        """Get session data for user"""
        key = f"session:{user_id}"
        data = await self.client.get(key)
        return json.loads(data) if data else None
    
    async def update_session_data(self, user_id: str, updates: dict):
        """Update specific fields in session data"""
        current = await self.get_session_data(user_id) or {}
        current.update(updates)
        await self.set_session_data(user_id, current)
    
    # ============ Idempotency (Anti-Duplicate) ============
    
    async def is_message_processed(self, message_id: str) -> bool:
        """Check if message was already processed (idempotency check)"""
        key = f"processed:{message_id}"
        return await self.client.exists(key) > 0
    
    async def mark_message_processed(
        self, 
        message_id: str, 
        ttl: int = 3600  # Keep for 1 hour
    ):
        """Mark message as processed to prevent duplicates"""
        key = f"processed:{message_id}"
        await self.client.setex(key, ttl, "1")
    
    # ============ Follow-up Tracking ============
    
    async def mark_for_followup(
        self, 
        user_id: str, 
        page_id: str,
        followup_count: int = 0
    ):
        """Add user to follow-up queue"""
        key = f"followup:{page_id}"
        data = {
            "user_id": user_id,
            "count": followup_count,
            "last_contact": "now"
        }
        await self.client.hset(key, user_id, json.dumps(data))
    
    async def get_followup_list(self, page_id: str) -> list[dict]:
        """Get all users needing follow-up for a page"""
        key = f"followup:{page_id}"
        data = await self.client.hgetall(key)
        return [json.loads(v) for v in data.values()]
    
    async def remove_from_followup(self, user_id: str, page_id: str):
        """Remove user from follow-up queue"""
        key = f"followup:{page_id}"
        await self.client.hdel(key, user_id)


# Global instance
redis_manager = RedisManager()
