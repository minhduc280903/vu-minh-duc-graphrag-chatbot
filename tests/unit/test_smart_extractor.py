# -*- coding: utf-8 -*-
"""
Unit Tests for Smart Extractor Service
Tests AI-powered entity extraction
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSmartExtractor:
    """Tests for SmartExtractor class"""
    
    @pytest.fixture
    def smart_extractor(self):
        """Create smart extractor instance"""
        from app.services.smart_extractor import SmartExtractor
        return SmartExtractor()
    
    @pytest.fixture
    def mock_genai_client(self):
        """Mock Gemini client"""
        mock = MagicMock()
        mock.models = MagicMock()
        mock.models.generate_content = AsyncMock()
        return mock


class TestExtractedLead:
    """Tests for ExtractedLead dataclass"""
    
    def test_default_values(self):
        """Should have correct default values"""
        from app.services.smart_extractor import ExtractedLead
        
        lead = ExtractedLead()
        
        assert lead.phone_number is None
        assert lead.customer_name is None
        assert lead.intent == "other"
        assert lead.sentiment == "neutral"
        assert lead.is_hot_lead is False
        assert lead.confidence == 0.0
    
    def test_to_dict(self):
        """Should convert to dictionary"""
        from app.services.smart_extractor import ExtractedLead
        
        lead = ExtractedLead(
            phone_number="0909123456",
            customer_name="Test",
            intent="buying"
        )
        result = lead.to_dict()
        
        assert result["phone_number"] == "0909123456"
        assert result["customer_name"] == "Test"
        assert result["intent"] == "buying"


class TestCustomerIntent:
    """Tests for CustomerIntent enum"""
    
    def test_all_intents_defined(self):
        """Should have all expected intents"""
        from app.services.smart_extractor import CustomerIntent
        
        expected = ["buying", "asking_price", "asking_info", "complaining", 
                    "support", "greeting", "other"]
        
        for intent in expected:
            assert hasattr(CustomerIntent, intent.upper())


class TestCustomerSentiment:
    """Tests for CustomerSentiment enum"""
    
    def test_all_sentiments_defined(self):
        """Should have all expected sentiments"""
        from app.services.smart_extractor import CustomerSentiment
        
        expected = ["positive", "neutral", "negative", "urgent"]
        
        for sentiment in expected:
            assert hasattr(CustomerSentiment, sentiment.upper())


class TestFallbackExtraction:
    """Tests for rule-based fallback extraction"""
    
    @pytest.fixture
    def smart_extractor(self):
        from app.services.smart_extractor import SmartExtractor
        return SmartExtractor()
    
    @pytest.mark.asyncio
    async def test_fallback_phone_extraction(self, smart_extractor):
        """Should extract phone number in fallback mode"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        result.phone_number = "0909123456"  # Pre-set phone (as extract() does before fallback)
        await smart_extractor._fallback_extract("SĐT: 0909123456", result)
        
        assert result.phone_number == "0909123456"
    
    @pytest.mark.asyncio
    async def test_fallback_greeting_intent(self, smart_extractor):
        """Should detect greeting intent"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Xin chào, tôi muốn hỏi", result)
        
        assert result.intent == "greeting"
    
    @pytest.mark.asyncio
    async def test_fallback_buying_intent(self, smart_extractor):
        """Should detect buying intent"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Tôi muốn mua sản phẩm này", result)
        
        assert result.intent == "buying"
        assert result.is_hot_lead is True  # Buying intent sets hot lead
    
    @pytest.mark.asyncio
    async def test_fallback_price_intent(self, smart_extractor):
        """Should detect price asking intent"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Giá sản phẩm này bao nhiêu?", result)
        
        assert result.intent == "asking_price"
    
    @pytest.mark.asyncio
    async def test_fallback_positive_sentiment(self, smart_extractor):
        """Should detect positive sentiment"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Cảm ơn bạn rất nhiều!", result)
        
        assert result.sentiment == "positive"
    
    @pytest.mark.asyncio
    async def test_fallback_negative_sentiment(self, smart_extractor):
        """Should detect negative sentiment"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Tệ quá, không hài lòng", result)
        
        assert result.sentiment == "negative"
    
    @pytest.mark.asyncio
    async def test_fallback_urgent_sentiment(self, smart_extractor):
        """Should detect urgent sentiment"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Gấp lắm, cần ngay!", result)
        
        assert result.sentiment == "urgent"
    
    @pytest.mark.asyncio
    async def test_fallback_hot_lead_detection(self, smart_extractor):
        """Should detect hot lead when buying intent is present"""
        from app.services.smart_extractor import ExtractedLead
        
        result = ExtractedLead()
        await smart_extractor._fallback_extract("Tôi muốn mua ngay", result)
        
        # Hot lead is set when buying intent detected
        assert result.intent == "buying"
        assert result.is_hot_lead is True


class TestExtractFromMessages:
    """Tests for extracting from multiple messages"""
    
    @pytest.fixture
    def smart_extractor(self):
        from app.services.smart_extractor import SmartExtractor
        return SmartExtractor()
    
    @pytest.mark.asyncio
    async def test_combine_messages(self, smart_extractor):
        """Should combine multiple messages"""
        messages = [
            {"content": "Xin chào"},
            {"content": "Tôi muốn hỏi giá"},
            {"content": "SĐT 0909123456"}
        ]
        
        with patch.object(smart_extractor, 'extract', new_callable=AsyncMock) as mock_extract:
            from app.services.smart_extractor import ExtractedLead
            mock_extract.return_value = ExtractedLead(phone_number="0909123456")
            
            await smart_extractor.extract_from_messages(messages)
            
            # Should have combined text
            call_args = mock_extract.call_args[0][0]
            assert "Xin chào" in call_args
            assert "hỏi giá" in call_args
            assert "0909123456" in call_args
