"""
Messenger API Service
Handles sending messages to Facebook Messenger
"""
from typing import Optional

import httpx
from loguru import logger

from app.config import get_settings

settings = get_settings()

# Updated to latest stable API version (2024)
MESSENGER_API_URL = "https://graph.facebook.com/v22.0/me/messages"


class MessengerAPI:
    """Facebook Messenger Send API wrapper"""
    
    async def send_text(
        self, 
        recipient_id: str, 
        text: str,
        typing_delay: bool = True
    ) -> bool:
        """
        Send text message to user
        
        Args:
            recipient_id: User's PSID
            text: Message text
            typing_delay: Whether to show typing indicator first
        """
        if typing_delay:
            await self.send_typing_on(recipient_id)
        
        return await self._send_message(recipient_id, {
            "text": text
        })
    
    async def send_image(
        self, 
        recipient_id: str, 
        image_url: str
    ) -> bool:
        """Send image attachment"""
        return await self._send_message(recipient_id, {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        })
    
    async def send_file(
        self, 
        recipient_id: str, 
        file_url: str
    ) -> bool:
        """Send file attachment (PDF, etc.)"""
        return await self._send_message(recipient_id, {
            "attachment": {
                "type": "file",
                "payload": {
                    "url": file_url,
                    "is_reusable": True
                }
            }
        })
    
    async def send_quick_replies(
        self, 
        recipient_id: str, 
        text: str,
        quick_replies: list
    ) -> bool:
        """
        Send message with quick reply buttons
        
        Args:
            quick_replies: List of dicts with 'title' and 'payload'
        """
        qr_payload = [
            {
                "content_type": "text",
                "title": qr["title"],
                "payload": qr.get("payload", qr["title"])
            }
            for qr in quick_replies
        ]
        
        return await self._send_message(recipient_id, {
            "text": text,
            "quick_replies": qr_payload
        })
    
    async def send_generic_template(
        self, 
        recipient_id: str, 
        elements: list
    ) -> bool:
        """
        Send product carousel with images and buttons
        
        Args:
            elements: List of product dicts with title, subtitle, image_url, buttons
        """
        return await self._send_message(recipient_id, {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        })
    
    async def send_typing_on(self, recipient_id: str) -> bool:
        """Show typing indicator"""
        return await self._send_action(recipient_id, "typing_on")
    
    async def send_typing_off(self, recipient_id: str) -> bool:
        """Hide typing indicator"""
        return await self._send_action(recipient_id, "typing_off")
    
    async def _send_message(
        self, 
        recipient_id: str, 
        message: dict,
        max_retries: int = 3
    ) -> bool:
        """
        Internal method to send message with retry logic
        
        Retry strategy (recommended by architect):
        - Retry 3 times with exponential backoff
        - Don't retry policy violations (400 errors)
        """
        if not settings.fb_page_access_token:
            logger.warning("No FB access token configured")
            return False
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": message,
            "messaging_type": "RESPONSE"
        }
        
        last_error = None
        delay = 2.0  # Initial delay
        
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        MESSENGER_API_URL,
                        params={"access_token": settings.fb_page_access_token},
                        json=payload,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        logger.debug(f"✅ Message sent to {recipient_id}")
                        return True
                    
                    # Check for non-retryable errors (policy violations)
                    error_data = response.json() if response.text else {}
                    error_code = error_data.get("error", {}).get("code", 0)
                    
                    # Error codes that shouldn't be retried:
                    # 10 = Permission denied, 200 = Message blocked, 551 = 24h window closed
                    non_retryable = [10, 200, 551, 190, 100]
                    
                    if response.status_code == 400 or error_code in non_retryable:
                        logger.error(f"❌ Non-retryable error: {response.text}")
                        return False
                    
                    last_error = response.text
                    
            except Exception as e:
                last_error = str(e)
            
            # Retry with backoff
            if attempt < max_retries:
                logger.warning(
                    f"⚠️ Send attempt {attempt}/{max_retries} failed. "
                    f"Retrying in {delay}s..."
                )
                import asyncio
                await asyncio.sleep(delay)
                delay = min(delay * 5, 60)  # Exponential backoff, max 60s
            else:
                logger.error(f"❌ All {max_retries} attempts failed: {last_error}")
        
        return False
    
    async def _send_action(
        self, 
        recipient_id: str, 
        action: str
    ) -> bool:
        """Send sender action (typing, seen, etc.)"""
        if not settings.fb_page_access_token:
            return False
        
        payload = {
            "recipient": {"id": recipient_id},
            "sender_action": action
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    MESSENGER_API_URL,
                    params={"access_token": settings.fb_page_access_token},
                    json=payload,
                    timeout=10
                )
                return response.status_code == 200
        except:
            return False
    
    async def get_user_profile(self, user_id: str) -> Optional[dict]:
        """
        Get user profile from Facebook
        Returns name, profile_pic if available
        """
        if not settings.fb_page_access_token:
            return None
        
        url = f"https://graph.facebook.com/v18.0/{user_id}"
        params = {
            "fields": "first_name,last_name,profile_pic",
            "access_token": settings.fb_page_access_token
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "first_name": data.get("first_name", ""),
                        "last_name": data.get("last_name", ""),
                        "full_name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                        "profile_pic": data.get("profile_pic")
                    }
        except Exception as e:
            logger.warning(f"Failed to get user profile: {e}")
        
        return None


# Global instance
messenger_api = MessengerAPI()
