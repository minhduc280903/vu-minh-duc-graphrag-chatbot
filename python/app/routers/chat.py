"""
Chat Router
Endpoints for chat processing triggered by n8n
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.services.ai_brain import ai_brain
from app.services.response_splitter import split_response
from app.services.smart_extractor import smart_extractor
from app.services.messenger_api import messenger_api

router = APIRouter()


class MessageInput(BaseModel):
    """Input model for chat processing"""
    user_id: str
    page_id: str
    messages: List[dict]  # Aggregated messages from debounce
    user_name: Optional[str] = None
    platform: str = "messenger"  # messenger or zalo


class ChatResponse(BaseModel):
    """Response model from AI processing"""
    response_parts: List[str]  # Split response parts
    has_product: bool = False
    products: List[dict] = []
    has_phone: bool = False
    phone_number: Optional[str] = None
    should_invite_zalo: bool = False
    # New fields from Smart Extractor
    customer_intent: str = "other"
    customer_sentiment: str = "neutral"
    is_hot_lead: bool = False
    keywords: List[str] = []


@router.post("/process", response_model=ChatResponse)
async def process_chat(input: MessageInput):
    """
    Main chat processing endpoint
    Called by n8n after debounce window expires
    
    Flow:
    1. Combine all buffered messages
    2. Process with AI (multimodal + GraphRAG)
    3. Extract phone if present
    4. Split response for human-like delivery
    5. Return structured response for n8n to send
    """
    logger.info(f"🧠 Processing chat for {input.user_id} ({len(input.messages)} messages)")
    
    try:
        # Combine message contents
        combined_context = []
        attachments = []

        for msg in input.messages:
            if msg.get("content"):
                combined_context.append(msg["content"])
            if msg.get("attachments"):
                attachments.extend(msg["attachments"])

        user_query = " ".join(combined_context)

        # Smart extraction with AI (phone, intent, sentiment, keywords)
        extracted = await smart_extractor.extract(user_query, input.user_name)

        has_phone = bool(extracted.phone_number)

        # Process with AI Brain (use extracted keywords for better GraphRAG)
        ai_response = await ai_brain.process(
            user_id=input.user_id,
            user_name=input.user_name or "bạn",
            query=user_query,
            attachments=attachments
        )

        # Split response for human-like delivery
        response_parts = split_response(ai_response.text)

        # Determine if we should invite to Zalo
        should_invite_zalo = has_phone and input.platform == "messenger"

        return ChatResponse(
            response_parts=response_parts,
            has_product=ai_response.has_products,
            products=ai_response.products,
            has_phone=has_phone,
            phone_number=extracted.phone_number,
            should_invite_zalo=should_invite_zalo,
            customer_intent=extracted.intent,
            customer_sentiment=extracted.sentiment,
            is_hot_lead=extracted.is_hot_lead,
            keywords=extracted.keywords
        )
        
    except Exception as e:
        logger.error(f"❌ Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-response")
async def send_response_parts(
    user_id: str,
    page_id: str,
    parts: List[str],
    products: List[dict] = None
):
    """
    Send response parts with delays (called by n8n loop)
    This endpoint is for n8n to call with each part
    """
    # This is typically handled by n8n's loop + wait nodes
    # But can be used for direct sending
    for i, part in enumerate(parts):
        await messenger_api.send_text(user_id, part)
        
        # Send product images if any
        if products and i == len(parts) - 1:
            for product in products:
                if product.get("image_url"):
                    await messenger_api.send_image(user_id, product["image_url"])
    
    return {"status": "sent", "parts_count": len(parts)}
