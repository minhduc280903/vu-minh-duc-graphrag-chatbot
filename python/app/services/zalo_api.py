"""
Zalo API Service
Handles Zalo OA messaging and ZNS notifications
"""
from typing import Optional, List

import httpx
from loguru import logger

from app.config import get_settings

settings = get_settings()

ZALO_OA_API = "https://openapi.zalo.me/v3.0/oa"
ZALO_ZNS_API = "https://business.openapi.zalo.me/message/template"


class ZaloAPI:
    """Zalo OA and ZNS API wrapper"""
    
    # ============ Zalo OA Methods ============
    
    async def send_text(
        self, 
        user_id: str, 
        text: str
    ) -> bool:
        """Send text message via Zalo OA"""
        payload = {
            "recipient": {"user_id": user_id},
            "message": {"text": text}
        }
        
        return await self._send_oa_message(payload)
    
    async def send_image(
        self, 
        user_id: str, 
        image_url: str
    ) -> bool:
        """Send image via Zalo OA"""
        payload = {
            "recipient": {"user_id": user_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "media",
                        "elements": [{
                            "media_type": "image",
                            "url": image_url
                        }]
                    }
                }
            }
        }
        
        return await self._send_oa_message(payload)
    
    async def send_list_template(
        self, 
        user_id: str, 
        elements: List[dict]
    ) -> bool:
        """
        Send product list template
        
        Args:
            elements: List of dicts with title, subtitle, image_url
        """
        payload = {
            "recipient": {"user_id": user_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "list",
                        "elements": elements
                    }
                }
            }
        }
        
        return await self._send_oa_message(payload)
    
    async def _send_oa_message(self, payload: dict) -> bool:
        """Internal method to send OA message"""
        if not settings.zalo_access_token:
            logger.warning("No Zalo access token configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{ZALO_OA_API}/message/cs",
                    headers={"access_token": settings.zalo_access_token},
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("error") == 0:
                        logger.debug("✅ Zalo OA message sent")
                        return True
                    else:
                        logger.error(f"❌ Zalo OA error: {data}")
                        return False
                else:
                    logger.error(f"❌ Zalo OA failed: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Zalo OA error: {e}")
            return False
    
    # ============ Zalo ZNS Methods (Notification Service) ============
    
    async def send_zns_notification(
        self,
        phone: str,
        template_data: dict
    ) -> bool:
        """
        Send ZNS notification to phone number
        Used for lead notifications to telesale
        
        Args:
            phone: Vietnamese phone number (84xxxxxxxxx format)
            template_data: Data to fill template placeholders
        """
        if not settings.zalo_access_token or not settings.zalo_zns_template_id:
            logger.warning("Zalo ZNS not configured")
            return False
        
        # Convert phone format
        if phone.startswith("0"):
            phone = "84" + phone[1:]
        
        payload = {
            "phone": phone,
            "template_id": settings.zalo_zns_template_id,
            "template_data": template_data
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ZALO_ZNS_API,
                    headers={"access_token": settings.zalo_access_token},
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("error") == 0:
                        logger.info(f"✅ ZNS sent to {phone}")
                        return True
                    else:
                        logger.error(f"❌ ZNS error: {data}")
                        return False
                else:
                    logger.error(f"❌ ZNS failed: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ ZNS error: {e}")
            return False
    
    async def notify_telesale(
        self,
        customer_name: str,
        customer_phone: str,
        source_page: str,
        conversation_summary: str = ""
    ) -> bool:
        """
        Notify telesale staff about new lead
        
        Uses Zalo ZNS in production, Telegram in demo mode (free)
        """
        settings = get_settings()
        
        # Check feature toggle - use Telegram instead of Zalo in demo mode
        if not settings.enable_zalo_zns:
            logger.info("📢 [DEMO MODE] Zalo ZNS disabled, using Telegram")
            
            if settings.enable_telegram_notify:
                try:
                    from app.services.telegram_notifier import telegram_notifier
                    return await telegram_notifier.notify_new_lead(
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        source=source_page,
                        summary=conversation_summary
                    )
                except Exception as e:
                    logger.warning(f"Telegram notify failed: {e}")
            
            # Fallback: just log the lead
            logger.info(f"📞 Lead: {customer_name} - {customer_phone} from {source_page}")
            return True
        
        # Production mode: Use Zalo ZNS
        telesale_phones = settings.telesale_phones.split(",")
        
        template_data = {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "source": source_page,
            "summary": conversation_summary[:200] if conversation_summary else "Khách quan tâm sản phẩm"
        }
        
        success = False
        for phone in telesale_phones:
            phone = phone.strip()
            if phone:
                result = await self.send_zns_notification(phone, template_data)
                success = success or result
        
        return success
    
    async def send_group_invite(
        self, 
        user_id: str,
        customer_name: str
    ) -> bool:
        """
        Send Zalo group invite link to customer
        """
        if not settings.zalo_group_link:
            logger.warning("Zalo group link not configured")
            return False
        
        message = (
            f"Cảm ơn {customer_name} đã quan tâm! 🎉\n\n"
            f"Để nhận ưu đãi độc quyền và hỗ trợ nhanh nhất, "
            f"mời bạn tham gia nhóm Zalo của chúng mình:\n\n"
            f"👉 {settings.zalo_group_link}"
        )
        
        return await self.send_text(user_id, message)


# Global instance
zalo_api = ZaloAPI()
