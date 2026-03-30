"""
Response Splitter Service
Splits AI responses into human-like message chunks
Creates natural conversation flow with typing indicators
"""
import re
import random
from typing import List

from loguru import logger


def split_response(
    text: str, 
    max_chars: int = 250,  # Max 250 chars per message (FB marketing policy)
    min_chars: int = 50
) -> List[str]:
    """
    Split AI response into natural message chunks
    
    Rules:
    1. Split on sentence boundaries (. ! ?)
    2. Keep related sentences together if under max_chars
    3. Never split mid-sentence
    4. Add slight variation to feel natural
    
    Args:
        text: The AI response to split
        max_chars: Maximum characters per chunk (FB limit is 2000)
        min_chars: Minimum characters per chunk (avoid too short messages)
    
    Returns:
        List of message parts ready to send
    """
    if not text:
        return []
    
    # Clean up text
    text = text.strip()
    
    # If short enough, return as single message
    if len(text) <= max_chars:
        return [text]
    
    # Split into sentences
    # Regex handles: . ! ? and Vietnamese punctuation
    sentence_pattern = r'(?<=[.!?।။။])\s+'
    sentences = re.split(sentence_pattern, text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # If adding this sentence exceeds max, start new chunk
        if current_chunk and len(current_chunk) + len(sentence) + 1 > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            # Add to current chunk
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Merge very short chunks with previous
    merged_chunks = []
    for chunk in chunks:
        if merged_chunks and len(chunk) < min_chars:
            # Merge with previous if combined length is ok
            if len(merged_chunks[-1]) + len(chunk) + 1 <= max_chars:
                merged_chunks[-1] += " " + chunk
            else:
                merged_chunks.append(chunk)
        else:
            merged_chunks.append(chunk)
    
    logger.debug(f"Split response into {len(merged_chunks)} parts")
    return merged_chunks


def split_response_vietnamese(text: str) -> List[str]:
    """
    Vietnamese-optimized splitting
    Handles Vietnamese punctuation and common patterns
    """
    if not text:
        return []
    
    # Vietnamese-specific patterns for natural breaks
    break_patterns = [
        r'(?<=[.!?])\s+',           # Standard punctuation
        r'(?<=\.\.\.\s)',           # Ellipsis
        r'(?<=:\s)',                # After colon with space
        r'(?<=;\s)',                # After semicolon
        r'(?<=\n)',                 # Line breaks
    ]
    
    # Combine patterns
    combined_pattern = '|'.join(break_patterns)
    
    # Split text
    parts = re.split(combined_pattern, text)
    
    # Clean and filter
    parts = [p.strip() for p in parts if p and p.strip()]
    
    # Group into reasonable chunks
    max_chars = 350
    chunks = []
    current = ""
    
    for part in parts:
        if len(current) + len(part) + 1 > max_chars and current:
            chunks.append(current)
            current = part
        else:
            current = f"{current} {part}".strip() if current else part
    
    if current:
        chunks.append(current)
    
    return chunks


def get_typing_delay(text: str) -> float:
    """
    Calculate realistic typing delay based on message length
    
    Average typing speed: ~40 words per minute
    Average word length: 5 characters
    So roughly 200 characters per minute = 3.3 chars/second
    
    Returns delay in seconds
    """
    base_delay = 1.5  # Minimum delay
    chars_per_second = 15  # Faster than real typing for better UX
    
    # Calculate based on length
    length_delay = len(text) / chars_per_second
    
    # Add randomness (±20%)
    variation = random.uniform(0.8, 1.2)
    
    # Cap at reasonable max
    delay = min(base_delay + (length_delay * variation), 5.0)
    
    return round(delay, 1)


def format_with_emojis(text: str) -> str:
    """
    Add appropriate emojis to response based on content
    Makes responses feel more friendly and human
    """
    # Greeting patterns
    if any(word in text.lower() for word in ["chào", "xin chào", "hello", "hi"]):
        if not any(e in text for e in ["👋", "😊", "🙂"]):
            text = "👋 " + text
    
    # Thank you patterns
    if any(word in text.lower() for word in ["cảm ơn", "thank"]):
        if not any(e in text for e in ["🙏", "❤️", "💕"]):
            text = text + " 🙏"
    
    # Product/price patterns
    if any(word in text.lower() for word in ["giá", "price", "sản phẩm", "product"]):
        if not any(e in text for e in ["💰", "🏷️", "📦"]):
            text = "🏷️ " + text
    
    return text
