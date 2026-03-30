"""
Smart Entity Extractor Service
Sử dụng Gemini AI Structured Output để trích xuất thông tin khách hàng chính xác
"""
import json
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from enum import Enum

from loguru import logger
from google import genai
from google.genai import types

from app.config import get_settings
from app.services.lead_extractor import extract_phone_number, is_valid_phone, normalize_phone


class CustomerIntent(str, Enum):
    """Phân loại ý định khách hàng"""
    BUYING = "buying"                    # Muốn mua hàng
    ASKING_PRICE = "asking_price"        # Hỏi giá
    ASKING_INFO = "asking_info"          # Hỏi thông tin sản phẩm
    COMPLAINING = "complaining"          # Khiếu nại
    SUPPORT = "support"                  # Cần hỗ trợ kỹ thuật
    GREETING = "greeting"                # Chào hỏi
    OTHER = "other"                      # Khác


class CustomerSentiment(str, Enum):
    """Phân loại cảm xúc khách hàng"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    URGENT = "urgent"                    # Cần xử lý gấp


@dataclass
class ExtractedLead:
    """Thông tin lead được trích xuất từ tin nhắn"""
    phone_number: Optional[str] = None
    customer_name: Optional[str] = None
    intent: str = CustomerIntent.OTHER.value
    sentiment: str = CustomerSentiment.NEUTRAL.value
    product_interests: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    is_hot_lead: bool = False            # Lead nóng cần ưu tiên
    confidence: float = 0.0
    raw_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class SmartExtractor:
    """
    Trích xuất thông tin khách hàng thông minh sử dụng Gemini AI

    Ưu điểm so với regex:
    - Hiểu ngữ cảnh tiếng Việt
    - Nhận diện SĐT viết bằng chữ ("không chín một hai...")
    - Phân loại ý định chính xác
    - Detect sentiment từ ngữ cảnh
    """

    def __init__(self):
        self.client: Optional[genai.Client] = None
        self._initialized = False
        self.settings = get_settings()

    async def initialize(self):
        """Khởi tạo Gemini client"""
        if self._initialized:
            return

        if not self.settings.google_api_key:
            logger.warning("⚠️ No Google API key for Smart Extractor")
            return

        try:
            self.client = genai.Client(api_key=self.settings.google_api_key)
            self._initialized = True
            logger.info("✅ Smart Extractor initialized")
        except Exception as e:
            logger.error(f"❌ Smart Extractor init failed: {e}")

    async def extract(self, text: str, user_name: Optional[str] = None) -> ExtractedLead:
        """
        Trích xuất thông tin từ tin nhắn khách hàng

        Args:
            text: Nội dung tin nhắn
            user_name: Tên khách từ Facebook/Zalo profile (nếu có)

        Returns:
            ExtractedLead với thông tin được trích xuất
        """
        result = ExtractedLead(raw_text=text)

        # Bước 1: Quick regex extraction (không cần AI)
        quick_phone = extract_phone_number(text)
        if quick_phone:
            result.phone_number = quick_phone
            result.is_hot_lead = True

        # Bước 2: AI extraction cho các trường hợp phức tạp
        await self.initialize()

        if not self._initialized:
            # Fallback: sử dụng rule-based extraction
            return await self._fallback_extract(text, result)

        try:
            # Schema cho Structured Output
            extraction_schema = {
                "type": "object",
                "properties": {
                    "phone_number": {
                        "type": "string",
                        "description": "Số điện thoại Việt Nam (10 số, bắt đầu bằng 0). Chuyển đổi từ chữ sang số nếu cần."
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Tên khách hàng nếu họ tự giới thiệu"
                    },
                    "intent": {
                        "type": "string",
                        "enum": ["buying", "asking_price", "asking_info", "complaining", "support", "greeting", "other"],
                        "description": "Ý định chính của khách hàng"
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "urgent"],
                        "description": "Cảm xúc của khách hàng"
                    },
                    "product_interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách sản phẩm/dịch vụ khách quan tâm"
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Các từ khóa quan trọng để tìm kiếm sản phẩm"
                    }
                },
                "required": ["intent", "sentiment"]
            }

            system_prompt = """Bạn là AI trích xuất thông tin khách hàng từ tin nhắn.

QUAN TRỌNG về số điện thoại:
- Nhận diện SĐT viết bằng chữ: "không chín không một hai ba bốn năm sáu bảy tám" = "0901234567"
- Nhận diện SĐT có dấu cách/gạch: "091 234 5678" hoặc "091-234-5678"
- Nhận diện SĐT có mã vùng: "+84 912345678" hoặc "84912345678" -> chuyển về "0912345678"
- Chỉ trả về SĐT hợp lệ Việt Nam (10 số, bắt đầu bằng 0)

Phân loại intent:
- buying: Muốn mua, đặt hàng, chốt đơn
- asking_price: Hỏi giá, báo giá
- asking_info: Hỏi thông tin, tư vấn sản phẩm
- complaining: Khiếu nại, phàn nàn về sản phẩm/dịch vụ
- support: Cần hỗ trợ kỹ thuật, hướng dẫn sử dụng
- greeting: Chào hỏi đơn thuần
- other: Không xác định

Phân loại sentiment:
- positive: Hài lòng, vui vẻ, cảm ơn
- neutral: Bình thường, hỏi thông tin
- negative: Không hài lòng, tức giận
- urgent: Cần xử lý gấp, khẩn cấp

Trả về JSON hợp lệ."""

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.settings.gemini_model,  # Use model from config
                contents=f"Trích xuất thông tin từ tin nhắn khách hàng:\n\n{text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=extraction_schema,
                    temperature=0.1  # Low temperature for extraction accuracy
                )
            )

            # Parse response
            data = json.loads(response.text)

            # Merge AI results with quick extraction
            ai_phone = data.get("phone_number")
            if ai_phone:
                normalized = normalize_phone(ai_phone)
                if normalized and is_valid_phone(normalized):
                    result.phone_number = normalized
                    result.is_hot_lead = True

            result.customer_name = data.get("customer_name") or user_name
            result.intent = data.get("intent", CustomerIntent.OTHER.value)
            result.sentiment = data.get("sentiment", CustomerSentiment.NEUTRAL.value)
            result.product_interests = data.get("product_interests", [])
            result.keywords = data.get("keywords", [])
            result.confidence = 0.95

            # Mark as hot lead if buying intent or has phone
            if result.intent == CustomerIntent.BUYING.value or result.phone_number:
                result.is_hot_lead = True

            logger.info(f"🎯 Extracted: intent={result.intent}, phone={result.phone_number}, hot={result.is_hot_lead}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ AI extraction JSON error: {e}")
            return await self._fallback_extract(text, result)
        except Exception as e:
            logger.error(f"❌ AI extraction error: {e}")
            return await self._fallback_extract(text, result)

    async def _fallback_extract(self, text: str, result: ExtractedLead) -> ExtractedLead:
        """Rule-based fallback khi AI không khả dụng"""
        text_lower = text.lower()

        # Intent detection
        if any(word in text_lower for word in ["mua", "đặt", "order", "chốt", "lấy"]):
            result.intent = CustomerIntent.BUYING.value
            result.is_hot_lead = True
        elif any(word in text_lower for word in ["giá", "bao nhiêu", "price", "báo giá"]):
            result.intent = CustomerIntent.ASKING_PRICE.value
        elif any(word in text_lower for word in ["khiếu nại", "phàn nàn", "lỗi", "hỏng", "tệ", "dở"]):
            result.intent = CustomerIntent.COMPLAINING.value
            result.sentiment = CustomerSentiment.NEGATIVE.value
        elif any(word in text_lower for word in ["hướng dẫn", "cách dùng", "sử dụng"]):
            result.intent = CustomerIntent.SUPPORT.value
        elif any(word in text_lower for word in ["chào", "hello", "hi ", "xin chào"]):
            result.intent = CustomerIntent.GREETING.value
        else:
            result.intent = CustomerIntent.ASKING_INFO.value

        # Sentiment detection
        if result.sentiment == CustomerSentiment.NEUTRAL.value:
            if any(word in text_lower for word in ["tốt", "hay", "đẹp", "thích", "cảm ơn", "thanks"]):
                result.sentiment = CustomerSentiment.POSITIVE.value
            elif any(word in text_lower for word in ["gấp", "khẩn", "ngay", "nhanh"]):
                result.sentiment = CustomerSentiment.URGENT.value

        # Keyword extraction (simple)
        keywords = []
        product_keywords = ["máy lọc", "nồi chiên", "robot", "điện thoại", "laptop", "tivi"]
        for kw in product_keywords:
            if kw in text_lower:
                keywords.append(kw)
        result.keywords = keywords

        result.confidence = 0.6
        return result

    async def extract_from_messages(self, messages: List[dict]) -> ExtractedLead:
        """
        Trích xuất từ nhiều tin nhắn (sau debounce)
        """
        # Combine all message contents
        combined_text = " ".join([
            msg.get("content", "") for msg in messages if msg.get("content")
        ])

        return await self.extract(combined_text)


# Global instance
smart_extractor = SmartExtractor()
