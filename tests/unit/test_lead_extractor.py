# -*- coding: utf-8 -*-
"""
Unit Tests for Lead Extractor Service
Tests Feature 2: Phone number extraction and contact info
"""
import pytest
from app.services.lead_extractor import (
    extract_phone_number,
    extract_all_phones,
    normalize_phone,
    is_valid_phone,
    format_phone_display,
    extract_contact_info
)


class TestExtractPhoneNumber:
    """Tests for extract_phone_number function"""
    
    def test_empty_text(self):
        """Empty text should return None"""
        assert extract_phone_number("") is None
        assert extract_phone_number(None) is None
    
    def test_standard_10_digit(self):
        """Standard 10-digit phone should be extracted"""
        text = "SĐT của tôi là 0909123456"
        result = extract_phone_number(text)
        assert result == "0909123456"
    
    def test_with_country_code_plus(self):
        """Phone with +84 should be normalized"""
        text = "Liên hệ +84912345678 nhé"
        result = extract_phone_number(text)
        assert result == "0912345678"
    
    def test_with_country_code_no_plus(self):
        """Phone with 84 prefix should be normalized"""
        text = "Gọi 84909123456"
        result = extract_phone_number(text)
        assert result == "0909123456"
    
    def test_with_spaces(self):
        """Phone with spaces should be extracted"""
        text = "Số: 0909 123 456"
        result = extract_phone_number(text)
        assert result == "0909123456"
    
    def test_with_dashes(self):
        """Phone with dashes should be extracted"""
        text = "số máy: 0909-123-456"
        result = extract_phone_number(text)
        assert result == "0909123456"
    
    def test_with_dots(self):
        """Phone with dots should be extracted"""
        text = "Liên hệ: 0909.123.456"
        result = extract_phone_number(text)
        assert result == "0909123456"
    
    def test_no_phone(self):
        """Text without phone should return None"""
        text = "Không có số điện thoại trong này"
        result = extract_phone_number(text)
        assert result is None
    
    def test_invalid_short_number(self):
        """Short numbers should not be extracted"""
        text = "Mã số 12345 không phải SĐT"
        result = extract_phone_number(text)
        assert result is None
    
    def test_viettel_prefix(self):
        """Viettel prefixes should be valid"""
        prefixes = ['032', '033', '034', '035', '036', '037', '038', '039', '086', '096', '097', '098']
        for prefix in prefixes:
            text = f"SĐT: {prefix}1234567"
            result = extract_phone_number(text)
            assert result == f"{prefix}1234567", f"Failed for prefix {prefix}"
    
    def test_vinaphone_prefix(self):
        """Vinaphone prefixes should be valid"""
        prefixes = ['081', '082', '083', '084', '085', '088', '091', '094']
        for prefix in prefixes:
            text = f"SĐT: {prefix}1234567"
            result = extract_phone_number(text)
            assert result == f"{prefix}1234567"
    
    def test_mobifone_prefix(self):
        """Mobifone prefixes should be valid"""
        prefixes = ['070', '076', '077', '078', '079', '089', '090', '093']
        for prefix in prefixes:
            text = f"SĐT: {prefix}1234567"
            result = extract_phone_number(text)
            assert result == f"{prefix}1234567"


class TestExtractAllPhones:
    """Tests for extract_all_phones function"""
    
    def test_multiple_phones(self):
        """Should extract all phones in text"""
        text = "Liên hệ 0909123456 hoặc 0912345678"
        result = extract_all_phones(text)
        assert len(result) == 2
        assert "0909123456" in result
        assert "0912345678" in result
    
    def test_single_phone(self):
        """Single phone should return list with one"""
        text = "SĐT: 0909123456"
        result = extract_all_phones(text)
        assert result == ["0909123456"]
    
    def test_no_duplicates(self):
        """Should not return duplicate phones"""
        text = "Gọi 0909123456, nhắc lại: 0909123456"
        result = extract_all_phones(text)
        assert result == ["0909123456"]


class TestNormalizePhone:
    """Tests for normalize_phone function"""
    
    def test_already_normalized(self):
        """Already normalized phone should be returned as-is"""
        assert normalize_phone("0909123456") == "0909123456"
    
    def test_remove_plus84(self):
        """Should convert +84 to 0"""
        assert normalize_phone("+84912345678") == "0912345678"
    
    def test_remove_84(self):
        """Should convert 84 to 0"""
        assert normalize_phone("84909123456") == "0909123456"
    
    def test_remove_special_chars(self):
        """Should remove spaces, dashes, dots"""
        assert normalize_phone("091-234-5678") == "0912345678"
        assert normalize_phone("091 234 5678") == "0912345678"
        assert normalize_phone("091.234.5678") == "0912345678"
    
    def test_add_leading_zero(self):
        """9-digit numbers should get leading 0"""
        assert normalize_phone("912345678") == "0912345678"
    
    def test_invalid_length(self):
        """Invalid lengths should return None"""
        assert normalize_phone("12345") is None
        assert normalize_phone("123456789012") is None


class TestIsValidPhone:
    """Tests for is_valid_phone function"""
    
    def test_valid_phones(self):
        """Valid Vietnamese phones should return True"""
        valid_phones = [
            "0909123456",  # Mobifone
            "0912345678",  # Vinaphone
            "0321234567",  # Viettel
            "0981234567",  # Viettel
        ]
        for phone in valid_phones:
            assert is_valid_phone(phone), f"{phone} should be valid"
    
    def test_invalid_prefix(self):
        """Invalid prefixes should return False"""
        assert is_valid_phone("0501234567") is False  # Invalid prefix
        assert is_valid_phone("0111234567") is False  # Invalid prefix
    
    def test_wrong_length(self):
        """Wrong length should return False"""
        assert is_valid_phone("090912345") is False  # 9 digits
        assert is_valid_phone("09091234567") is False  # 11 digits
    
    def test_empty_or_none(self):
        """Empty or None should return False"""
        assert is_valid_phone("") is False
        assert is_valid_phone(None) is False


class TestFormatPhoneDisplay:
    """Tests for format_phone_display function"""
    
    def test_format_standard(self):
        """Should format as XXX XXX XXXX"""
        assert format_phone_display("0912345678") == "091 234 5678"
    
    def test_already_formatted(self):
        """Already formatted should not change"""
        result = format_phone_display("091 234 5678")
        # Since it's not 10 continuous digits, returns as-is
        assert result == "091 234 5678"
    
    def test_invalid_input(self):
        """Invalid input should return as-is"""
        assert format_phone_display("12345") == "12345"
        assert format_phone_display("") == ""


class TestExtractContactInfo:
    """Tests for extract_contact_info function"""
    
    def test_phone_only(self):
        """Should extract phone without Zalo mention"""
        text = "SĐT: 0909123456"
        result = extract_contact_info(text)
        assert result["phone"] == "0909123456"
        assert result["has_zalo"] is False
        assert result["phone_count"] == 1
    
    def test_phone_with_zalo(self):
        """Should detect Zalo mention"""
        text = "Zalo 0909123456 nhé"
        result = extract_contact_info(text)
        assert result["phone"] == "0909123456"
        assert result["has_zalo"] is True
    
    def test_multiple_phones(self):
        """Should return all phones"""
        text = "SĐT 0909123456 hoặc Zalo 0912345678"
        result = extract_contact_info(text)
        assert result["phone"] == "0909123456"  # First phone
        assert len(result["all_phones"]) == 2
        assert result["has_zalo"] is True
    
    def test_no_contact(self):
        """No contact info should return empty"""
        text = "Không có thông tin liên hệ"
        result = extract_contact_info(text)
        assert result["phone"] is None
        assert result["phone_count"] == 0
        assert result["has_zalo"] is False
