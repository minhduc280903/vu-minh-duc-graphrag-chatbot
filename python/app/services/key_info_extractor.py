"""
Key Info Extractor Service
Extracts important customer information from conversations for long-term memory
Based on architect recommendation for Hybrid Memory (short-term + long-term)
"""
from dataclasses import dataclass, field
from typing import Optional, List
import re

from loguru import logger

from app.config import get_settings
from app.services.lead_extractor import extract_phone_number


@dataclass
class CustomerKeyInfo:
    """Structured customer information for long-term storage"""
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    interests: List[str] = field(default_factory=list)
    intent: Optional[str] = None  # buying, asking_price, complaining, etc.
    sentiment: Optional[str] = None  # positive, neutral, negative
    source_page: Optional[str] = None
    conversation_summary: Optional[str] = None


async def extract_key_info_with_llm(
    messages: List[dict],
    user_id: str,
    llm_client=None
) -> CustomerKeyInfo:
    """
    Use LLM to extract key information from conversation
    This is called after debounce to analyze the full context
    """
    settings = get_settings()
    
    # Combine all message contents
    conversation_text = "\n".join([
        f"Khách: {m.get('content', '')}" 
        for m in messages 
        if m.get("content")
    ])
    
    # Basic extraction first (no LLM needed)
    key_info = CustomerKeyInfo(user_id=user_id)
    
    # Extract phone number
    for msg in messages:
        content = msg.get("content", "")
        if content:
            phone = extract_phone_number(content)
            if phone:
                key_info.phone = phone
                break
    
    # If no LLM client, return basic info
    if not llm_client:
        return key_info
    
    # Use LLM for advanced extraction
    try:
        prompt = f"""
        Phân tích lịch sử hội thoại sau và trích xuất thông tin khách hàng.
        Trả về JSON với các trường:
        - name: Tên khách (nếu có nhắc đến)
        - phone: Số điện thoại (nếu có)
        - interests: Danh sách sản phẩm/dịch vụ họ quan tâm
        - intent: Ý định (buying|asking_price|asking_info|complaining|other)
        - sentiment: Cảm xúc (positive|neutral|negative)
        
        Lịch sử hội thoại:
        {conversation_text}
        
        Trả về JSON hợp lệ, không có text thừa.
        """
        
        response = await llm_client.ainvoke(prompt)
        
        # Parse response
        import json
        try:
            data = json.loads(response.content)
            key_info.name = data.get("name")
            key_info.phone = data.get("phone") or key_info.phone
            key_info.interests = data.get("interests", [])
            key_info.intent = data.get("intent")
            key_info.sentiment = data.get("sentiment")
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            
    except Exception as e:
        logger.error(f"LLM key info extraction failed: {e}")
    
    return key_info


def extract_name_from_text(text: str) -> Optional[str]:
    """
    Simple regex-based name extraction
    Looks for patterns like "Mình là X", "Tên em là Y", etc.
    """
    patterns = [
        r"(?:mình|em|anh|chị|tôi)\s+(?:là|tên)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)",
        r"(?:tên\s+(?:mình|em|anh|chị|tôi)\s+là)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
        if match:
            return match.group(1).strip()
    
    return None


def detect_intent(text: str) -> str:
    """
    Simple keyword-based intent detection
    """
    text_lower = text.lower()
    
    if any(word in text_lower for word in ["mua", "đặt", "order", "chốt"]):
        return "buying"
    elif any(word in text_lower for word in ["giá", "bao nhiêu", "price", "báo giá"]):
        return "asking_price"
    elif any(word in text_lower for word in ["khiếu nại", "phàn nàn", "lỗi", "hỏng", "tệ"]):
        return "complaining"
    elif any(word in text_lower for word in ["hỏi", "thông tin", "tư vấn", "?"]):
        return "asking_info"
    else:
        return "other"


def detect_sentiment(text: str) -> str:
    """
    Simple keyword-based sentiment detection
    """
    text_lower = text.lower()
    
    positive_words = ["tốt", "hay", "đẹp", "thích", "ok", "oke", "được", "cảm ơn", "thanks"]
    negative_words = ["tệ", "xấu", "ghét", "không thích", "chán", "lỗi", "hỏng"]
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"
