"""
Lead Extractor Service
Extracts phone numbers and contact information from messages
Supports Vietnamese phone number formats
"""
import re
from typing import Optional, List, Dict

from loguru import logger


# Vietnamese phone number patterns
PHONE_PATTERNS = [
    # 10-digit format (new format since 2018)
    r'\b(0[1-9][0-9]{8})\b',
    
    # With country code
    r'\b(\+84[1-9][0-9]{8})\b',
    r'\b(84[1-9][0-9]{8})\b',
    
    # With spaces/dashes
    r'\b(0[1-9][0-9]{2}[\s.-]?[0-9]{3}[\s.-]?[0-9]{3})\b',
    
    # With parentheses
    r'\b\(?0[1-9][0-9]{2}\)?[\s.-]?[0-9]{3}[\s.-]?[0-9]{3}\b',
]

# Common Vietnamese carrier prefixes (10-digit)
VALID_PREFIXES = [
    # Viettel
    '032', '033', '034', '035', '036', '037', '038', '039', '086', '096', '097', '098',
    # Vinaphone
    '081', '082', '083', '084', '085', '088', '091', '094',
    # Mobifone
    '070', '076', '077', '078', '079', '089', '090', '093',
    # Vietnamobile
    '052', '056', '058', '092',
    # Gmobile
    '059', '099',
    # Itelecom
    '087',
]


def extract_phone_number(text: str) -> Optional[str]:
    """
    Extract Vietnamese phone number from text
    
    Args:
        text: Message text to search
    
    Returns:
        Normalized phone number (10 digits starting with 0) or None
    """
    if not text:
        return None
    
    # Try each pattern
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Normalize the match
            normalized = normalize_phone(match)
            if normalized and is_valid_phone(normalized):
                logger.info(f"📞 Extracted phone: {normalized}")
                return normalized
    
    return None


def extract_all_phones(text: str) -> List[str]:
    """Extract all phone numbers from text"""
    phones = []
    
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            normalized = normalize_phone(match)
            if normalized and is_valid_phone(normalized) and normalized not in phones:
                phones.append(normalized)
    
    return phones


def normalize_phone(phone: str) -> Optional[str]:
    """
    Normalize phone number to 10-digit format
    
    Examples:
    - +84912345678 -> 0912345678
    - 84912345678 -> 0912345678
    - 091 234 5678 -> 0912345678
    """
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Handle country code
    if digits.startswith('84') and len(digits) == 11:
        digits = '0' + digits[2:]
    elif digits.startswith('84') and len(digits) == 10:
        digits = '0' + digits[2:]
    
    # Ensure starts with 0
    if not digits.startswith('0') and len(digits) == 9:
        digits = '0' + digits
    
    # Validate length
    if len(digits) != 10:
        return None
    
    return digits


def is_valid_phone(phone: str) -> bool:
    """
    Validate Vietnamese phone number
    
    Args:
        phone: Normalized 10-digit phone number
    
    Returns:
        True if valid Vietnamese mobile number
    """
    if not phone or len(phone) != 10:
        return False
    
    # Check prefix
    prefix = phone[:3]
    return prefix in VALID_PREFIXES


def format_phone_display(phone: str) -> str:
    """
    Format phone for display
    
    Example: 0912345678 -> 091 234 5678
    """
    if not phone or len(phone) != 10:
        return phone
    
    return f"{phone[:3]} {phone[3:6]} {phone[6:]}"


def extract_contact_info(text: str) -> Dict:
    """
    Extract comprehensive contact info from text
    
    Returns dict with:
    - phone: Primary phone number
    - all_phones: All found phone numbers
    - has_zalo: Whether user mentioned Zalo
    """
    phones = extract_all_phones(text)
    
    # Check for Zalo mentions
    zalo_pattern = r'\b(zalo|za lo|z a l o)\b'
    has_zalo = bool(re.search(zalo_pattern, text, re.IGNORECASE))
    
    return {
        "phone": phones[0] if phones else None,
        "all_phones": phones,
        "has_zalo": has_zalo,
        "phone_count": len(phones)
    }


# ============ LLM-based extraction (fallback) ============

async def extract_phone_with_llm(text: str, llm_client) -> Optional[str]:
    """
    Use LLM to extract phone number when regex fails
    Useful for creative formats like "không chín không một hai ba bốn..."
    """
    prompt = f"""
    Trích xuất số điện thoại từ đoạn văn sau (nếu có).
    Chỉ trả về số điện thoại dạng 10 chữ số, không có ký tự khác.
    Nếu không có số điện thoại, trả về "NONE".
    
    Văn bản: {text}
    
    Số điện thoại:
    """
    
    try:
        response = await llm_client.generate(prompt)
        result = response.strip()
        
        if result != "NONE" and len(result) == 10 and result.isdigit():
            return result
    except Exception as e:
        logger.warning(f"LLM phone extraction failed: {e}")
    
    return None
