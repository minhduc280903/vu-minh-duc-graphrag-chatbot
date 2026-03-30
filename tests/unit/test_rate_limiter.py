# -*- coding: utf-8 -*-
"""
Unit Tests for Rate Limiter Service
Tests spam protection and rate limiting per user
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestUserRateLimiter:
    """Tests for UserRateLimiter class"""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter with default settings"""
        from app.services.rate_limiter import UserRateLimiter
        return UserRateLimiter(
            max_messages_per_minute=10,
            max_messages_per_hour=100,
            mute_duration_minutes=5
        )
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Create mocked redis manager"""
        mock = MagicMock()
        mock.client = AsyncMock()
        mock.client.exists = AsyncMock(return_value=0)
        mock.client.incr = AsyncMock(return_value=1)
        mock.client.expire = AsyncMock(return_value=True)
        mock.client.ttl = AsyncMock(return_value=60)
        mock.client.setex = AsyncMock(return_value=True)
        mock.client.delete = AsyncMock(return_value=1)
        mock.client.get = AsyncMock(return_value=None)
        return mock
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_redis_manager):
        """Should allow request within limits"""
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            result = await rate_limiter.check_rate_limit("user123", "page456")
            
            assert result["allowed"] is True
            assert result["reason"] is None
            assert result["remaining"] >= 0
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_muted_user(self, rate_limiter, mock_redis_manager):
        """Should block muted user"""
        mock_redis_manager.client.exists = AsyncMock(return_value=1)  # User is muted
        mock_redis_manager.client.ttl = AsyncMock(return_value=300)
        
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            result = await rate_limiter.check_rate_limit("user123", "page456")
            
            assert result["allowed"] is False
            assert result["reason"] == "rate_limited_muted"
            assert result["reset_at"] == 300
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_minute_exceeded(self, rate_limiter, mock_redis_manager):
        """Should block when minute limit exceeded"""
        mock_redis_manager.client.exists = AsyncMock(return_value=0)
        mock_redis_manager.client.incr = AsyncMock(return_value=11)  # Over limit
        
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            with patch.object(rate_limiter, '_mute_user', new_callable=AsyncMock) as mock_mute:
                result = await rate_limiter.check_rate_limit("user123", "page456")
                
                assert result["allowed"] is False
                assert result["reason"] == "rate_limited_minute"
                mock_mute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_hour_exceeded(self, rate_limiter, mock_redis_manager):
        """Should block when hour limit exceeded"""
        mock_redis_manager.client.exists = AsyncMock(return_value=0)
        
        # First call for minute (under limit), second for hour (over limit)
        mock_redis_manager.client.incr = AsyncMock(side_effect=[5, 101])
        
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            with patch.object(rate_limiter, '_mute_user', new_callable=AsyncMock) as mock_mute:
                result = await rate_limiter.check_rate_limit("user123", "page456")
                
                assert result["allowed"] is False
                assert result["reason"] == "rate_limited_hour"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_no_redis(self, rate_limiter):
        """Should allow when Redis is not available"""
        mock_manager = MagicMock()
        mock_manager.client = None
        
        with patch('app.services.rate_limiter.redis_manager', mock_manager):
            result = await rate_limiter.check_rate_limit("user123", "page456")
            
            assert result["allowed"] is True
            assert result["remaining"] == -1
    
    @pytest.mark.asyncio
    async def test_mute_user(self, rate_limiter, mock_redis_manager):
        """Should mute user with correct duration"""
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            with patch('app.services.rate_limiter.telegram_notifier') as mock_telegram:
                mock_telegram.send_message = AsyncMock(return_value=True)
                
                await rate_limiter._mute_user("user123", "page456")
                
                mock_redis_manager.client.setex.assert_called()
    
    @pytest.mark.asyncio
    async def test_unmute_user(self, rate_limiter, mock_redis_manager):
        """Should unmute user by deleting key"""
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            await rate_limiter.unmute_user("user123", "page456")
            
            mock_redis_manager.client.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_stats(self, rate_limiter, mock_redis_manager):
        """Should return user rate limit stats"""
        mock_redis_manager.client.get = AsyncMock(side_effect=["5", "50"])
        mock_redis_manager.client.exists = AsyncMock(return_value=0)
        
        with patch('app.services.rate_limiter.redis_manager', mock_redis_manager):
            result = await rate_limiter.get_user_stats("user123", "page456")
            
            assert result["minute_count"] == 5
            assert result["hour_count"] == 50
            assert result["is_muted"] is False
            assert result["max_per_minute"] == 10
            assert result["max_per_hour"] == 100
    
    @pytest.mark.asyncio
    async def test_get_user_stats_no_redis(self, rate_limiter):
        """Should return defaults when Redis not available"""
        mock_manager = MagicMock()
        mock_manager.client = None
        
        with patch('app.services.rate_limiter.redis_manager', mock_manager):
            result = await rate_limiter.get_user_stats("user123", "page456")
            
            assert result["minute_count"] == 0
            assert result["hour_count"] == 0
            assert result["is_muted"] is False


class TestRateLimiterConfiguration:
    """Tests for rate limiter configuration"""
    
    def test_custom_limits(self):
        """Should accept custom limits"""
        from app.services.rate_limiter import UserRateLimiter
        
        limiter = UserRateLimiter(
            max_messages_per_minute=5,
            max_messages_per_hour=50,
            mute_duration_minutes=10
        )
        
        assert limiter.max_per_minute == 5
        assert limiter.max_per_hour == 50
        assert limiter.mute_duration == 10
    
    def test_default_limits(self):
        """Should use default limits"""
        from app.services.rate_limiter import UserRateLimiter
        
        limiter = UserRateLimiter()
        
        assert limiter.max_per_minute == 10
        assert limiter.max_per_hour == 100
        assert limiter.mute_duration == 5
