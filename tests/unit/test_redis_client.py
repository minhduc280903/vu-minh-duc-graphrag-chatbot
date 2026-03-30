# -*- coding: utf-8 -*-
"""
Unit Tests for Redis Client Service
Tests Feature 6: Session Management and Feature 8: Debouncing
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRedisManager:
    """Tests for RedisManager class"""
    
    @pytest.fixture
    def redis_manager(self):
        """Create fresh redis manager for each test"""
        from app.services.redis_client import RedisManager
        return RedisManager()
    
    @pytest.mark.asyncio
    async def test_connect(self, redis_manager):
        """Should connect to Redis successfully"""
        with patch('redis.asyncio.Redis') as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_redis.return_value = mock_client
            
            await redis_manager.connect("localhost", 6379, "password")
            
            assert redis_manager.client is not None
            mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, redis_manager):
        """Should disconnect from Redis"""
        redis_manager.client = AsyncMock()
        redis_manager.client.close = AsyncMock()
        
        await redis_manager.disconnect()
        
        redis_manager.client.close.assert_called_once()


class TestDebounceBuffer:
    """Tests for debounce buffer operations"""
    
    @pytest.fixture
    def redis_manager_with_client(self):
        """Create redis manager with mocked client"""
        from app.services.redis_client import RedisManager
        manager = RedisManager()
        manager.client = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_add_message_to_buffer(self, redis_manager_with_client):
        """Should add message to buffer and return all messages"""
        manager = redis_manager_with_client
        manager.client.rpush = AsyncMock(return_value=1)
        manager.client.expire = AsyncMock(return_value=True)
        manager.client.lrange = AsyncMock(return_value=[
            json.dumps({"type": "text", "content": "Hello"})
        ])
        
        message = {"type": "text", "content": "Hello"}
        result = await manager.add_message_to_buffer("user123", message, 7)
        
        assert len(result) == 1
        assert result[0]["content"] == "Hello"
        manager.client.rpush.assert_called_once()
        manager.client.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_and_clear_buffer(self, redis_manager_with_client):
        """Should get all messages and clear buffer"""
        manager = redis_manager_with_client
        manager.client.lrange = AsyncMock(return_value=[
            json.dumps({"type": "text", "content": "Msg 1"}),
            json.dumps({"type": "text", "content": "Msg 2"})
        ])
        manager.client.delete = AsyncMock(return_value=1)
        
        result = await manager.get_and_clear_buffer("user123")
        
        assert len(result) == 2
        assert result[0]["content"] == "Msg 1"
        assert result[1]["content"] == "Msg 2"
        manager.client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_has_pending_messages_true(self, redis_manager_with_client):
        """Should return True when buffer has messages"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=1)
        
        result = await manager.has_pending_messages("user123")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_has_pending_messages_false(self, redis_manager_with_client):
        """Should return False when buffer is empty"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=0)
        
        result = await manager.has_pending_messages("user123")
        
        assert result is False


class TestAdminHandover:
    """Tests for admin handover operations"""
    
    @pytest.fixture
    def redis_manager_with_client(self):
        from app.services.redis_client import RedisManager
        manager = RedisManager()
        manager.client = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_set_admin_handover(self, redis_manager_with_client):
        """Should set admin handover flag with TTL"""
        manager = redis_manager_with_client
        manager.client.setex = AsyncMock(return_value=True)
        
        await manager.set_admin_handover("page123", "user456", minutes=30)
        
        manager.client.setex.assert_called_once()
        args = manager.client.setex.call_args[0]
        assert "admin_handover:page123:user456" in args[0]
        assert args[1] == 30 * 60  # 30 minutes in seconds
    
    @pytest.mark.asyncio
    async def test_is_admin_active_true(self, redis_manager_with_client):
        """Should return True when admin is active"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=1)
        
        result = await manager.is_admin_active("page123", "user456")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_admin_active_false(self, redis_manager_with_client):
        """Should return False when admin is not active"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=0)
        
        result = await manager.is_admin_active("page123", "user456")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_clear_admin_handover(self, redis_manager_with_client):
        """Should clear admin handover flag"""
        manager = redis_manager_with_client
        manager.client.delete = AsyncMock(return_value=1)
        
        await manager.clear_admin_handover("page123", "user456")
        
        manager.client.delete.assert_called_once()


class TestSessionData:
    """Tests for session data operations"""
    
    @pytest.fixture
    def redis_manager_with_client(self):
        from app.services.redis_client import RedisManager
        manager = RedisManager()
        manager.client = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_set_session_data(self, redis_manager_with_client):
        """Should store session data with TTL"""
        manager = redis_manager_with_client
        manager.client.setex = AsyncMock(return_value=True)
        
        data = {"name": "Test User", "lang": "vi"}
        await manager.set_session_data("user123", data, ttl=3600)
        
        manager.client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_data_exists(self, redis_manager_with_client):
        """Should return session data when exists"""
        manager = redis_manager_with_client
        manager.client.get = AsyncMock(return_value=json.dumps({"name": "Test"}))
        
        result = await manager.get_session_data("user123")
        
        assert result["name"] == "Test"
    
    @pytest.mark.asyncio
    async def test_get_session_data_not_exists(self, redis_manager_with_client):
        """Should return None when session doesn't exist"""
        manager = redis_manager_with_client
        manager.client.get = AsyncMock(return_value=None)
        
        result = await manager.get_session_data("user123")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_session_data(self, redis_manager_with_client):
        """Should merge updates with existing data"""
        manager = redis_manager_with_client
        manager.client.get = AsyncMock(return_value=json.dumps({"name": "Test"}))
        manager.client.setex = AsyncMock(return_value=True)
        
        await manager.update_session_data("user123", {"lang": "vi"})
        
        # Should have called setex with merged data
        manager.client.setex.assert_called_once()


class TestIdempotency:
    """Tests for message idempotency check"""
    
    @pytest.fixture
    def redis_manager_with_client(self):
        from app.services.redis_client import RedisManager
        manager = RedisManager()
        manager.client = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_is_message_processed_true(self, redis_manager_with_client):
        """Should return True for already processed message"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=1)
        
        result = await manager.is_message_processed("msg123")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_is_message_processed_false(self, redis_manager_with_client):
        """Should return False for new message"""
        manager = redis_manager_with_client
        manager.client.exists = AsyncMock(return_value=0)
        
        result = await manager.is_message_processed("msg123")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_mark_message_processed(self, redis_manager_with_client):
        """Should mark message as processed with TTL"""
        manager = redis_manager_with_client
        manager.client.setex = AsyncMock(return_value=True)
        
        await manager.mark_message_processed("msg123", ttl=3600)
        
        manager.client.setex.assert_called_once()


class TestFollowup:
    """Tests for follow-up tracking"""
    
    @pytest.fixture
    def redis_manager_with_client(self):
        from app.services.redis_client import RedisManager
        manager = RedisManager()
        manager.client = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_mark_for_followup(self, redis_manager_with_client):
        """Should add user to follow-up queue"""
        manager = redis_manager_with_client
        manager.client.hset = AsyncMock(return_value=1)
        
        await manager.mark_for_followup("user123", "page456", followup_count=1)
        
        manager.client.hset.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_followup_list(self, redis_manager_with_client):
        """Should return list of users needing follow-up"""
        manager = redis_manager_with_client
        manager.client.hgetall = AsyncMock(return_value={
            "user1": json.dumps({"user_id": "user1", "count": 0}),
            "user2": json.dumps({"user_id": "user2", "count": 1})
        })
        
        result = await manager.get_followup_list("page123")
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_remove_from_followup(self, redis_manager_with_client):
        """Should remove user from follow-up queue"""
        manager = redis_manager_with_client
        manager.client.hdel = AsyncMock(return_value=1)
        
        await manager.remove_from_followup("user123", "page456")
        
        manager.client.hdel.assert_called_once()
