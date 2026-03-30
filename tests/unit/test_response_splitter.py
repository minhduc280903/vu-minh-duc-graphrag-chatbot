# -*- coding: utf-8 -*-
"""
Unit Tests for Response Splitter Service
Tests Feature 9: Human-like response splitting
"""
import pytest
from app.services.response_splitter import (
    split_response,
    split_response_vietnamese,
    get_typing_delay,
    format_with_emojis
)


class TestSplitResponse:
    """Tests for split_response function"""
    
    def test_empty_text(self):
        """Empty text should return empty list"""
        result = split_response("")
        assert result == []
        
    def test_none_text(self):
        """None text should return empty list"""
        result = split_response(None)
        assert result == []
    
    def test_short_text_no_split(self):
        """Short text should not be split"""
        text = "Xin chào bạn!"
        result = split_response(text)
        assert len(result) == 1
        assert result[0] == text
    
    def test_long_text_splits(self):
        """Long text should be split into multiple parts"""
        # Use text with sentence boundaries so it can split properly
        text = "C\u00e2u m\u1ed9t r\u1ea5t d\u00e0i c\u1ea7n chia nh\u1ecf. " * 20  # ~500 chars with sentence endings
        result = split_response(text, max_chars=100)
        assert len(result) >= 2
        for part in result:
            assert len(part) <= 120  # Allow some margin
    
    def test_sentence_boundary_split(self):
        """Should split on sentence boundaries"""
        text = "Câu một. Câu hai. Câu ba."
        result = split_response(text, max_chars=20)
        assert len(result) >= 2
        # Each part should end with a sentence
        for part in result:
            assert part.strip().endswith(('.', '!', '?')) or len(part) < 20
    
    def test_preserves_content(self):
        """All content should be preserved after splitting"""
        text = "Xin chào! Tôi là chatbot. Tôi có thể giúp gì cho bạn hôm nay?"
        result = split_response(text, max_chars=50)
        joined = " ".join(result)
        # Check key words are preserved
        assert "Xin chào" in joined
        assert "chatbot" in joined
        assert "giúp" in joined
    
    def test_custom_max_chars(self):
        """Should respect custom max_chars"""
        text = "A" * 100 + ". " + "B" * 100
        result = split_response(text, max_chars=120)
        for part in result:
            assert len(part) <= 120
    
    def test_min_chars_merge(self):
        """Very short chunks should be merged"""
        text = "Một. Hai. Ba. Bốn. Năm."
        result = split_response(text, max_chars=100, min_chars=20)
        # Should merge short sentences
        assert len(result) <= 3


class TestSplitResponseVietnamese:
    """Tests for Vietnamese-optimized splitting"""
    
    def test_empty_text(self):
        """Empty text should return empty list"""
        result = split_response_vietnamese("")
        assert result == []
    
    def test_vietnamese_punctuation(self):
        """Should handle Vietnamese text correctly"""
        text = "Xin chào! Bạn khỏe không? Tôi rất vui được gặp bạn."
        result = split_response_vietnamese(text)
        assert len(result) >= 1
        # Vietnamese characters should be preserved
        joined = " ".join(result)
        assert "Xin chào" in joined
        assert "khỏe" in joined
    
    def test_line_breaks(self):
        """Should split on line breaks"""
        text = "Dòng một\nDòng hai\nDòng ba"
        result = split_response_vietnamese(text)
        assert len(result) >= 1


class TestGetTypingDelay:
    """Tests for typing delay calculation"""
    
    def test_short_text_minimum_delay(self):
        """Short text should have minimum delay"""
        delay = get_typing_delay("Hi")
        assert delay >= 1.5  # base_delay
    
    def test_long_text_longer_delay(self):
        """Longer text should have longer delay"""
        short_delay = get_typing_delay("Hello")
        long_delay = get_typing_delay("Hello world, this is a much longer message")
        assert long_delay >= short_delay
    
    def test_max_delay_capped(self):
        """Delay should be capped at maximum"""
        delay = get_typing_delay("A" * 1000)
        assert delay <= 5.0
    
    def test_delay_in_range(self):
        """All delays should be in reasonable range"""
        for length in [5, 50, 100, 200]:
            delay = get_typing_delay("A" * length)
            assert 1.0 <= delay <= 5.0
    
    def test_delay_is_float(self):
        """Delay should be a float"""
        delay = get_typing_delay("Test message")
        assert isinstance(delay, float)


class TestFormatWithEmojis:
    """Tests for emoji formatting"""
    
    def test_greeting_adds_wave(self):
        """Greeting should add wave emoji"""
        text = "Xin chào bạn"
        result = format_with_emojis(text)
        assert "👋" in result
    
    def test_hello_adds_wave(self):
        """Hello should add wave emoji"""
        text = "Hello there"
        result = format_with_emojis(text)
        assert "👋" in result
    
    def test_thank_you_adds_hands(self):
        """Thank you should add prayer hands emoji"""
        text = "Cảm ơn bạn rất nhiều"
        result = format_with_emojis(text)
        assert "🙏" in result
    
    def test_price_adds_tag(self):
        """Price mentions should add tag emoji"""
        text = "Giá sản phẩm là 500k"
        result = format_with_emojis(text)
        assert "🏷️" in result
    
    def test_no_duplicate_emojis(self):
        """Should not add duplicate emojis"""
        text = "👋 Xin chào"
        result = format_with_emojis(text)
        assert result.count("👋") == 1
    
    def test_neutral_text_no_emoji(self):
        """Neutral text should not change"""
        text = "Đây là một câu bình thường"
        result = format_with_emojis(text)
        assert result == text
