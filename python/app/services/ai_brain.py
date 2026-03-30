"""
AI Brain Service
Core AI processing with Gemini 2.0 Flash and GraphRAG (SDK: google-genai)
"""
import base64
import json
import os
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional, Any

import httpx
from loguru import logger
from google import genai
from google.genai import types

from app.config import get_settings
from app.services.neo4j_client import neo4j_manager

settings = get_settings()

@dataclass
class AIResponse:
    """Structured AI response"""
    text: str # Full response text (combined chunks)
    response_parts: List[str] = field(default_factory=list) # Split chunks
    has_products: bool = False
    products: List[dict] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    confidence: float = 0.0

class AIBrain:
    """
    Main AI processing engine using Gemini 2.0 Flash
    Uses function calling and structured outputs for precision
    """
    
    def __init__(self):
        self.client: Optional[genai.Client] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize AI models"""
        if self._initialized:
            return
        
        if not settings.google_api_key:
            logger.warning("⚠️ No Google API key configured")
            return
        
        try:
            # Initialize Client (v1alpha/v1beta auto-selected by SDK for new models)
            self.client = genai.Client(api_key=settings.google_api_key)
            
            self._initialized = True
            logger.info(f"✅ AI Brain initialized with {settings.gemini_model}")
            
        except Exception as e:
            logger.error(f"❌ AI Brain initialization failed: {e}")
    
    async def process(
        self,
        user_id: str,
        user_name: str,
        query: str,
        attachments: List[dict] = None
    ) -> AIResponse:
        """
        Main processing pipeline using Gemini 2.0 Structured Output
        """
        await self.initialize()
        
        if not self._initialized:
            return AIResponse(text="Hệ thống đang bảo trì...")
        
        try:
            # Step 1: Prepare Context (GraphRAG + Attachments)
            # Short-circuit: Simple query analysis first to save GraphRAG if clear greeting
            
            # Analyze attachments (Native Multimodal - Image + Audio)
            attachment_parts = []
            if attachments:
                for att in attachments:
                    att_type = att.get("type")
                    att_url = att.get("url")
                    
                    if not att_url:
                        continue
                    
                    try:
                        async with httpx.AsyncClient() as http_client:
                            media_resp = await http_client.get(att_url, timeout=30)
                            media_bytes = media_resp.content
                            
                            if att_type == "image":
                                # Native image processing
                                attachment_parts.append(
                                    types.Part.from_bytes(data=media_bytes, mime_type="image/jpeg")
                                )
                                logger.debug(f"🖼️ Added image attachment ({len(media_bytes)} bytes)")
                                
                            elif att_type == "audio":
                                # Native audio processing (Gemini 2.0 Flash multimodal)
                                # Supports: audio/mp3, audio/wav, audio/ogg, audio/m4a
                                mime_type = self._detect_audio_mime(att_url)
                                attachment_parts.append(
                                    types.Part.from_bytes(data=media_bytes, mime_type=mime_type)
                                )
                                logger.info(f"🎤 Added audio attachment ({len(media_bytes)} bytes, {mime_type})")
                                
                            elif att_type == "video":
                                # Video with audio - extract first frame + audio context
                                # For now, we'll process as video bytes
                                attachment_parts.append(
                                    types.Part.from_bytes(data=media_bytes, mime_type="video/mp4")
                                )
                                logger.debug(f"🎬 Added video attachment ({len(media_bytes)} bytes)")
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to fetch attachment {att_type}: {e}")
            
            # Extract basic entities for GraphRAG (simple heuristic or fast LLM call)
            # For speed in 2.0 Flash, we might skip separate entity extraction and ask for it in main call
            # BUT GraphRAG needs entities BEFORE generating answer.
            # We'll do a quick entity extraction or keyword search.
            entities = await self._simple_entity_extraction(query)
            graph_context = await self._get_graph_context(entities)
            
            # Step 2: Build Main Prompt
            system_prompt = self._build_system_prompt(user_name, graph_context)
            
            # Step 3: Define Structured Output Schema
            # We ask AI to return: 
            # 1. Replies (chunks)
            # 2. Lead info (if any)
            # 3. Product intent (boolean)
            response_schema = {
                "type": "object",
                "properties": {
                    "replies": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "Các đoạn tin nhắn trả lời, chia nhỏ tự nhiên."
                    },
                    "has_product_intent": {
                        "type": "boolean",
                        "description": "True nếu khách hỏi về sản phẩm cụ thể."
                    }
                },
                "required": ["replies", "has_product_intent"]
            }

            # Step 4: Call Gemini 2.0 Flash
            contents = [query]
            if attachment_parts:
                contents.extend(attachment_parts)
                
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.3
                )
            )
            
            # Parse response
            try:
                data = json.loads(response.text)
                replies = data.get("replies", [])
                full_text = " ".join(replies)
                
                # Extract products from Graph Context if intent matches
                products = []
                if data.get("has_product_intent") and graph_context.get("products"):
                    products = self._extract_products_from_context(graph_context)

                return AIResponse(
                    text=full_text,
                    response_parts=replies,
                    has_products=len(products) > 0,
                    products=products,
                    entities=entities,
                    confidence=0.95
                )
            except json.JSONDecodeError:
                # Fallback if model fails strict JSON
                return AIResponse(text=response.text, response_parts=[response.text])

        except Exception as e:
            logger.error(f"❌ AI processing error: {e}")
            return AIResponse(text="Dạ, bạn có thể nói lại rõ hơn được không ạ?")

    async def _simple_entity_extraction(self, text: str) -> List[str]:
        """Simple keyword/entity extraction"""
        # Improved: Use Gemini 2.0 Flash specifically for this if cheap enough
        # Or just regex/basic logic. Let's use simple logic + maybe one quick LLM call in future.
        # For now, let's just split query to find potential keywords if we don't want another LLM call
        # OR use the 'model' again.
        # Let's simple split for now to verify integration first.
        # User requested 2.0 Flash. It's fast. Let's do a quick call?
        # No, let's keep it simple for now to avoid Rate Limits during tests.
        # We will split by common delimiters.
        return [w for w in text.split() if len(w) > 3][:3]

    async def _get_graph_context(self, entities: List[str]) -> dict:
        """Query Neo4j GraphRAG"""
        if not entities: return {}
        try:
            results = await neo4j_manager.answer_question_with_graph(question="", entities=entities)
            return {"products": results, "has_context": len(results) > 0}
        except Exception as e:
            logger.warning(f"GraphRAG error: {e}")
            return {}

    def _build_system_prompt(self, user_name: str, graph_context: dict) -> str:
        prompt = f"""Bạn là chatbot bán hàng thân thiện. Khách tên: {user_name}.

HƯỚNG DẪN XỬ LÝ ĐA PHƯƠNG THỨC:
- Nếu có ẢNH: Mô tả và phân tích hình ảnh trong context câu hỏi của khách.
- Nếu có AUDIO/VOICE: NGHE KỸ nội dung âm thanh và phản hồi dựa trên những gì khách NÓI trong đoạn ghi âm.
- Nếu có VIDEO: Phân tích cả hình ảnh lẫn âm thanh.

QUAN TRỌNG: Khi khách gửi voice message, hãy TÓM TẮT những gì họ nói và trả lời câu hỏi/yêu cầu của họ.

Trả lời tự nhiên, ngắn gọn, chia thành 2-3 câu. Dùng Emoji vui vẻ.
"""
        
        if graph_context.get("products"):
            prompt += "\nThông tin sản phẩm:\n"
            for p in graph_context["products"]:
                prompt += f"- {p.get('product_name')} ({p.get('price')}đ): {p.get('description')}\n"
                
        return prompt

    def _detect_audio_mime(self, url: str) -> str:
        """Detect audio MIME type from URL extension"""
        url_lower = url.lower()
        if ".mp3" in url_lower:
            return "audio/mp3"
        elif ".wav" in url_lower:
            return "audio/wav"
        elif ".ogg" in url_lower or ".opus" in url_lower:
            return "audio/ogg"
        elif ".m4a" in url_lower:
            return "audio/m4a"
        elif ".aac" in url_lower:
            return "audio/aac"
        elif ".webm" in url_lower:
            return "audio/webm"
        else:
            # Default to mp4 audio (common for Messenger voice messages)
            return "audio/mp4"

    def _extract_products_from_context(self, graph_context: dict) -> List[dict]:
        products = []
        for p in graph_context.get("products", []):
            if p.get("product_image"):
                products.append({
                    "name": p.get("product_name"),
                    "price": p.get("price"),
                    "image_url": p.get("product_image")
                })
        return products

# Global instance
ai_brain = AIBrain()
