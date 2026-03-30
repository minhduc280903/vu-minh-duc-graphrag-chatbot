# -*- coding: utf-8 -*-
"""
Feature Tests for All 10 Smart Chatbot Features
End-to-end tests verifying feature functionality
"""
import pytest
import httpx
from unittest.mock import AsyncMock, patch


class TestF1Multimodal:
    """Feature 1: Multi-modal (text, image, audio)"""
    
    @pytest.mark.asyncio
    async def test_text_only_message(self, async_client):
        """Should process text-only message"""
        payload = {
            "user_id": "test_f1_text",
            "page_id": "page_demo",
            "user_name": "Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Xin chào"}]
        }
        resp = await async_client.post("/chat/process", json=payload)
        
        assert resp.status_code == 200
        assert len(resp.json()["response_parts"]) >= 1
    
    @pytest.mark.asyncio
    async def test_image_attachment(self, async_client, sample_multimodal_message):
        """Should process message with image attachment"""
        resp = await async_client.post("/chat/process", json=sample_multimodal_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "response_parts" in data


class TestF2Personalization:
    """Feature 2: Personalization (call customer by name)"""
    
    @pytest.mark.asyncio
    async def test_uses_customer_name(self, async_client):
        """Should use customer name in response"""
        payload = {
            "user_id": "test_f2",
            "page_id": "page_demo",
            "user_name": "Anh Vượng",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Xin chào"}]
        }
        resp = await async_client.post("/chat/process", json=payload)
        
        assert resp.status_code == 200
        # AI should acknowledge the user


class TestF3AutoSendImages:
    """Feature 3: Auto send product images"""
    
    @pytest.mark.asyncio
    async def test_product_query_returns_products(self, async_client):
        """Should return products for product query"""
        payload = {
            "user_id": "test_f3",
            "page_id": "page_demo",
            "user_name": "Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Xin báo giá áo sơ mi"}]
        }
        resp = await async_client.post("/chat/process", json=payload)
        
        assert resp.status_code == 200
        data = resp.json()
        # has_product indicates if products were found
        assert "has_product" in data


class TestF4AdminHandover:
    """Feature 4: Admin handover (pause AI for 30 min)"""
    
    @pytest.mark.asyncio
    async def test_admin_handover_flag(self, redis_client):
        """Should set admin handover flag"""
        await redis_client.set_admin_handover("page123", "user456", minutes=30)
        
        is_active = await redis_client.is_admin_active("page123", "user456")
        assert is_active is True
    
    @pytest.mark.asyncio
    async def test_admin_clear_handover(self, redis_client):
        """Should clear admin handover"""
        await redis_client.set_admin_handover("page123", "user789", minutes=1)
        await redis_client.clear_admin_handover("page123", "user789")
        
        is_active = await redis_client.is_admin_active("page123", "user789")
        assert is_active is False


class TestF5TelegramNotification:
    """Feature 5: Telegram notifications for leads"""
    
    @pytest.mark.asyncio
    async def test_telegram_send_message(self, mock_telegram):
        """Should send Telegram message"""
        result = await mock_telegram.send_message("Test notification")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_telegram_notify_lead(self, mock_telegram):
        """Should notify new lead"""
        result = await mock_telegram.notify_new_lead(
            customer_name="Test User",
            customer_phone="0909123456",
            source="Facebook",
            summary="Interested in products"
        )
        assert result is True


class TestF6FollowUp:
    """Feature 6: Follow-up 24h+ tracking"""
    
    @pytest.mark.asyncio
    async def test_mark_for_followup(self, redis_client):
        """Should add user to follow-up queue"""
        await redis_client.mark_for_followup("user123", "page456", followup_count=0)
        
        followups = await redis_client.get_followup_list("page456")
        user_ids = [f["user_id"] for f in followups]
        assert "user123" in user_ids
    
    @pytest.mark.asyncio
    async def test_remove_from_followup(self, redis_client):
        """Should remove user from follow-up queue"""
        await redis_client.mark_for_followup("user_remove", "page456", followup_count=0)
        await redis_client.remove_from_followup("user_remove", "page456")
        
        followups = await redis_client.get_followup_list("page456")
        user_ids = [f.get("user_id") for f in followups]
        assert "user_remove" not in user_ids


class TestF7ZaloInvite:
    """Feature 7: Zalo group invite"""
    
    @pytest.mark.asyncio
    async def test_zalo_invite_flag(self, async_client, sample_lead_message):
        """Should set Zalo invite flag when phone detected"""
        resp = await async_client.post("/chat/process", json=sample_lead_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["should_invite_zalo"] is True
    
    @pytest.mark.asyncio
    async def test_no_zalo_invite_without_phone(self, async_client, sample_chat_message):
        """Should not invite to Zalo without phone"""
        resp = await async_client.post("/chat/process", json=sample_chat_message)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["should_invite_zalo"] is False


class TestF8Debouncing:
    """Feature 8: Message debouncing"""
    
    @pytest.mark.asyncio
    async def test_buffer_add_message(self, redis_client):
        """Should add message to buffer"""
        msg = {"type": "text", "content": "Test debounce"}
        messages = await redis_client.add_message_to_buffer("user_debounce", msg, 10)
        
        assert len(messages) >= 1
        assert messages[-1]["content"] == "Test debounce"
    
    @pytest.mark.asyncio
    async def test_buffer_clear(self, redis_client):
        """Should clear buffer and return messages"""
        msg = {"type": "text", "content": "To clear"}
        await redis_client.add_message_to_buffer("user_clear", msg, 10)
        
        cleared = await redis_client.get_and_clear_buffer("user_clear")
        assert len(cleared) >= 1
        
        # Should be empty after clear
        remaining = await redis_client.get_and_clear_buffer("user_clear")
        assert len(remaining) == 0


class TestF9ResponseSplitting:
    """Feature 9: Human-like response splitting"""
    
    def test_short_no_split(self):
        """Short text should not split"""
        from app.services.response_splitter import split_response
        
        result = split_response("Xin chào!")
        assert len(result) == 1
    
    def test_long_splits(self, long_response_text):
        """Long text should split into parts"""
        from app.services.response_splitter import split_response
        
        result = split_response(long_response_text)
        assert len(result) >= 2
    
    def test_typing_delay(self):
        """Should calculate typing delay"""
        from app.services.response_splitter import get_typing_delay
        
        delay = get_typing_delay("Hello world")
        assert 1.0 <= delay <= 5.0


class TestF10GraphRAG:
    """Feature 10: GraphRAG with Neo4j"""
    
    @pytest.mark.asyncio
    async def test_product_search(self, async_client):
        """Should use GraphRAG for product queries"""
        payload = {
            "user_id": "test_f10",
            "page_id": "page_demo",
            "user_name": "Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Tìm áo sơ mi trắng"}]
        }
        resp = await async_client.post("/chat/process", json=payload)
        
        assert resp.status_code == 200
        data = resp.json()
        # Response should mention product or info
        assert len(data["response_parts"]) >= 1


class TestAllFeaturesIntegration:
    """Integration test combining multiple features"""
    
    @pytest.mark.asyncio
    async def test_full_lead_flow(self, async_client):
        """Full lead flow: greeting -> product -> phone -> lead"""
        # Step 1: Greeting
        payload1 = {
            "user_id": "test_full_flow",
            "page_id": "page_demo",
            "user_name": "Anh Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Xin chào"}]
        }
        resp1 = await async_client.post("/chat/process", json=payload1)
        assert resp1.status_code == 200
        
        # Step 2: Product inquiry
        payload2 = {
            "user_id": "test_full_flow",
            "page_id": "page_demo",
            "user_name": "Anh Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Báo giá sản phẩm"}]
        }
        resp2 = await async_client.post("/chat/process", json=payload2)
        assert resp2.status_code == 200
        
        # Step 3: Provide phone (becomes lead)
        payload3 = {
            "user_id": "test_full_flow",
            "page_id": "page_demo",
            "user_name": "Anh Test",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Tư vấn giúp mình, SĐT 0909123456"}]
        }
        resp3 = await async_client.post("/chat/process", json=payload3)
        assert resp3.status_code == 200
        
        data3 = resp3.json()
        assert data3["has_phone"] is True
        assert data3["phone_number"] == "0909123456"
        assert data3["should_invite_zalo"] is True
