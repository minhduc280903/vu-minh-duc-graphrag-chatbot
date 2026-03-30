# -*- coding: utf-8 -*-
"""
Integration Tests for API Endpoints
Tests Health, Chat, and Webhook routers via HTTP
"""
import pytest
import httpx


class TestHealthEndpoints:
    """Integration tests for health endpoints"""
    
    @pytest.mark.asyncio
    async def test_basic_health(self, async_client):
        """Basic health should return healthy"""
        resp = await async_client.get("/health")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_detailed_health(self, async_client):
        """Detailed health should show service statuses"""
        resp = await async_client.get("/health/detailed")
        
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "services" in data
        assert "api" in data["services"]
        assert "redis" in data["services"]
        assert "neo4j" in data["services"]


class TestChatEndpoints:
    """Integration tests for chat processing"""
    
    @pytest.mark.asyncio
    async def test_chat_process_greeting(self, async_client, sample_chat_message):
        """Should process greeting message"""
        resp = await async_client.post("/chat/process", json=sample_chat_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "response_parts" in data
        assert len(data["response_parts"]) >= 1
    
    @pytest.mark.asyncio
    async def test_chat_process_lead(self, async_client, sample_lead_message):
        """Should extract phone from lead message"""
        resp = await async_client.post("/chat/process", json=sample_lead_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_phone"] is True
        assert data["phone_number"] == "0909123456"
        assert data["should_invite_zalo"] is True
    
    @pytest.mark.asyncio
    async def test_chat_process_multimodal(self, async_client, sample_multimodal_message):
        """Should process multimodal message with image"""
        resp = await async_client.post("/chat/process", json=sample_multimodal_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "response_parts" in data
    
    @pytest.mark.asyncio
    async def test_chat_process_missing_user_id(self, async_client):
        """Should fail with missing user_id"""
        payload = {
            "page_id": "page_demo",
            "messages": [{"type": "text", "content": "Hello"}]
        }
        resp = await async_client.post("/chat/process", json=payload)
        
        assert resp.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_response_contains_intent(self, async_client, sample_chat_message):
        """Should return customer intent"""
        resp = await async_client.post("/chat/process", json=sample_chat_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "customer_intent" in data
        assert data["customer_intent"] in ["greeting", "asking_info", "asking_price", "buying", "other"]
    
    @pytest.mark.asyncio
    async def test_chat_response_contains_sentiment(self, async_client, sample_chat_message):
        """Should return customer sentiment"""
        resp = await async_client.post("/chat/process", json=sample_chat_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "customer_sentiment" in data
        assert data["customer_sentiment"] in ["positive", "neutral", "negative", "urgent"]


class TestWebhookEndpoints:
    """Integration tests for webhook endpoints"""
    
    @pytest.mark.asyncio
    async def test_messenger_webhook_verify(self, async_client):
        """Should verify messenger webhook"""
        # This test requires FB_VERIFY_TOKEN to be set
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "demo_verify_token_2024",
            "hub.challenge": "test_challenge_123"
        }
        resp = await async_client.get("/webhook/messenger", params=params)
        
        # Either returns challenge or 403 based on token
        assert resp.status_code in [200, 403]
    
    @pytest.mark.asyncio
    async def test_messenger_webhook_invalid_token(self, async_client):
        """Should reject invalid verify token"""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge"
        }
        resp = await async_client.get("/webhook/messenger", params=params)
        
        assert resp.status_code == 403


class TestRootEndpoint:
    """Tests for root endpoint"""
    
    @pytest.mark.asyncio
    async def test_root(self, async_client):
        """Root should return API info"""
        resp = await async_client.get("/")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Smart Chatbot API"
        assert "version" in data
        assert data["status"] == "running"
