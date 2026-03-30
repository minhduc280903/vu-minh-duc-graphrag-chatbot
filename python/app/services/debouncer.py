"""
Debouncer Service
Aggregates multiple rapid messages before processing
Implements sliding window technique for "waiting for user to finish typing"
"""
import asyncio
from typing import Dict, Callable, Any
from datetime import datetime

from loguru import logger

from app.config import get_settings
from app.services.redis_client import redis_manager


class DebounceProcessor:
    """
    Debounce processor using Redis for persistence
    
    Flow:
    1. Message arrives -> Add to buffer
    2. Reset timer to DEBOUNCE_SECONDS
    3. When timer expires -> Process all buffered messages
    4. Clear buffer
    """
    
    def __init__(self):
        self.pending_tasks: Dict[str, asyncio.Task] = {}
        self.process_callback: Callable = None
    
    def set_callback(self, callback: Callable):
        """Set the callback function to call when debounce window expires"""
        self.process_callback = callback
    
    async def add_message(
        self, 
        user_id: str, 
        page_id: str,
        message: dict
    ):
        """
        Add message to debounce buffer
        Resets the debounce timer with smart detection
        """
        settings = get_settings()  # Get fresh settings
        buffer_key = f"{page_id}:{user_id}"
        
        # Determine debounce time based on message content
        content = message.get("content", "") or ""
        
        # Smart debounce: shorter wait for complete questions
        if content.strip().endswith("?"):
            debounce_time = settings.debounce_quick_seconds
            logger.debug(f"Quick debounce ({debounce_time}s) for question: {content[:30]}...")
        else:
            debounce_time = settings.debounce_seconds
        
        # Add message to Redis buffer
        messages = await redis_manager.add_message_to_buffer(
            user_id=buffer_key,
            message=message,
            debounce_seconds=debounce_time
        )
        
        logger.debug(f"Buffer for {user_id}: {len(messages)} messages")
        
        # Cancel existing timer if any
        if buffer_key in self.pending_tasks:
            self.pending_tasks[buffer_key].cancel()
        
        # Start new timer with appropriate debounce time
        logger.info(f"🚀 Creating debounce task for {buffer_key}, debounce={debounce_time}s")
        self.pending_tasks[buffer_key] = asyncio.create_task(
            self._wait_and_process(user_id, page_id, buffer_key, debounce_time)
        )
        logger.info(f"✅ Task created, total pending: {len(self.pending_tasks)}")
    
    async def _wait_and_process(
        self,
        user_id: str,
        page_id: str,
        buffer_key: str,
        debounce_time: int = 7
    ):
        """Wait for debounce period then trigger processing"""
        logger.info(f"⏳ Task STARTED for {buffer_key}, sleeping {debounce_time}s...")
        try:
            # Wait for debounce period (using passed time, not global settings)
            await asyncio.sleep(debounce_time)
            logger.info(f"⏳ Sleep DONE for {buffer_key}, getting buffer...")

            # Get all buffered messages
            messages = await redis_manager.get_and_clear_buffer(buffer_key)
            logger.info(f"📦 Buffer returned {len(messages)} messages for {buffer_key}")
            
            if messages:
                logger.info(
                    f"⏰ Debounce complete for {user_id}: "
                    f"Processing {len(messages)} messages"
                )
                
                # Call the processing callback (or send to n8n)
                if self.process_callback:
                    await self.process_callback(
                        user_id=user_id,
                        page_id=page_id,
                        messages=messages
                    )
                else:
                    # Default: Send to n8n webhook
                    await self._send_to_n8n(user_id, page_id, messages)
            
        except asyncio.CancelledError:
            # Timer was reset by new message
            logger.debug(f"Debounce timer reset for {user_id}")
        except Exception as e:
            logger.error(f"Debounce processing error: {e}")
        finally:
            # Cleanup
            self.pending_tasks.pop(buffer_key, None)
    
    async def _send_to_n8n(
        self,
        user_id: str,
        page_id: str,
        messages: list
    ):
        """Process with AI and send directly via Messenger API - Full Featured"""
        import httpx
        from app.services.messenger_api import messenger_api
        from app.services.zalo_api import zalo_api
        from app.config import get_settings

        settings = get_settings()

        try:
            # Step 0: Get user profile (personalization)
            user_name = "bạn"
            try:
                profile = await messenger_api.get_user_profile(user_id)
                if profile and profile.get("first_name"):
                    user_name = profile["first_name"]
                    logger.info(f"👤 Got user profile: {user_name}")
            except Exception as e:
                logger.warning(f"Could not get user profile: {e}")

            async with httpx.AsyncClient() as client:
                # Step 1: Call local API to process with AI
                logger.info(f"🧠 Calling AI for {user_id} ({user_name})...")
                process_response = await client.post(
                    "http://127.0.0.1:8000/chat/process",
                    json={
                        "user_id": user_id,
                        "page_id": page_id,
                        "messages": messages,
                        "user_name": user_name,
                        "platform": "messenger"
                    },
                    timeout=60
                )

                if process_response.status_code != 200:
                    logger.error(f"AI processing failed: {process_response.status_code}")
                    await self._process_directly(user_id, page_id, messages)
                    return

                ai_result = process_response.json()
                response_parts = ai_result.get("response_parts", [])
                products = ai_result.get("products", [])
                is_hot_lead = ai_result.get("is_hot_lead", False)
                phone_number = ai_result.get("phone_number")
                should_invite_zalo = ai_result.get("should_invite_zalo", False)
                customer_intent = ai_result.get("customer_intent", "other")

                logger.info(f"✅ AI response: {len(response_parts)} parts, hot_lead={is_hot_lead}")

                # Step 2: Send directly via Messenger API (human-like)
                for i, part in enumerate(response_parts):
                    # Send with typing indicator (built into send_text)
                    success = await messenger_api.send_text(user_id, part)
                    if success:
                        logger.info(f"📤 Sent part {i+1}/{len(response_parts)} to {user_id}")
                    else:
                        logger.error(f"❌ Failed to send part {i+1} to {user_id}")

                    # Human-like delay between messages
                    if i < len(response_parts) - 1:
                        await asyncio.sleep(2)

                # Step 3: Send product images if any
                for product in products:
                    if product.get("image_url"):
                        await messenger_api.send_image(user_id, product["image_url"])
                        logger.info(f"🖼️ Sent product image: {product.get('name', 'unknown')}")
                        await asyncio.sleep(1)

                # Step 4: Notify telesale if hot lead
                if is_hot_lead and phone_number:
                    logger.info(f"🔥 Hot lead detected! Notifying telesale...")
                    combined_query = " ".join(m.get("content", "") for m in messages if m.get("content"))
                    await zalo_api.notify_telesale(
                        customer_name=user_name,
                        customer_phone=phone_number,
                        source_page=f"Messenger Page {page_id}",
                        conversation_summary=combined_query[:200]
                    )

                # Step 5: Send Zalo group invite if should invite
                if should_invite_zalo and settings.zalo_group_link:
                    await asyncio.sleep(2)
                    invite_msg = (
                        f"Để nhận ưu đãi và hỗ trợ nhanh nhất, mời {user_name} "
                        f"tham gia nhóm Zalo của shop:\n👉 {settings.zalo_group_link}"
                    )
                    await messenger_api.send_text(user_id, invite_msg)
                    logger.info(f"📲 Sent Zalo group invite to {user_id}")

                logger.info(f"✅ All messages sent to {user_id}")

        except Exception as e:
            logger.error(f"Failed to process/send: {e}")
            # Fallback: Process directly
            await self._process_directly(user_id, page_id, messages)
    
    async def _process_directly(
        self, 
        user_id: str, 
        page_id: str,
        messages: list
    ):
        """Fallback: Process messages directly without n8n"""
        from app.services.ai_brain import ai_brain
        from app.services.response_splitter import split_response
        from app.services.messenger_api import messenger_api
        
        # Combine messages
        combined = " ".join(
            m.get("content", "") for m in messages if m.get("content")
        )
        attachments = []
        for m in messages:
            if m.get("attachments"):
                attachments.extend(m["attachments"])
        
        # Process with AI
        response = await ai_brain.process(
            user_id=user_id,
            user_name="bạn",
            query=combined,
            attachments=attachments
        )
        
        # Split and send
        parts = split_response(response.text)
        for part in parts:
            await messenger_api.send_text(user_id, part)
            await asyncio.sleep(2)  # Human-like delay


# Global instance
debounce_processor = DebounceProcessor()
