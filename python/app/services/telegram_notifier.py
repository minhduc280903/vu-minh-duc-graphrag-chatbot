"""
Telegram Notification Service
Free alternative to Zalo ZNS for lead notifications
"""
from typing import Optional

import httpx
from loguru import logger

from app.config import get_settings


class TelegramNotifier:
    """
    Telegram Bot API wrapper for lead notifications
    
    Free alternative to Zalo ZNS:
    - No per-message cost
    - Easy to set up (just create a bot with @BotFather)
    - Can send to groups/channels
    """
    
    TELEGRAM_API = "https://api.telegram.org/bot{token}"
    
    async def send_message(
        self, 
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML"
    ) -> bool:
        """
        Send message to Telegram chat/group
        
        Args:
            text: Message text (supports HTML formatting)
            chat_id: Target chat ID (uses config default if None)
            parse_mode: HTML or Markdown
        """
        settings = get_settings()
        
        if not settings.telegram_bot_token:
            logger.warning("⚠️ Telegram bot token not configured")
            return False
        
        target_chat = chat_id or settings.telegram_chat_id
        if not target_chat:
            logger.warning("⚠️ Telegram chat ID not configured")
            return False
        
        url = f"{self.TELEGRAM_API.format(token=settings.telegram_bot_token)}/sendMessage"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": target_chat,
                        "text": text,
                        "parse_mode": parse_mode
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Telegram message sent to {target_chat}")
                    return True
                else:
                    logger.error(f"❌ Telegram error: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Telegram API error: {e}")
            return False
    
    async def notify_new_lead(
        self,
        customer_name: str,
        customer_phone: str,
        source: str = "Facebook Messenger",
        summary: str = ""
    ) -> bool:
        """
        Send formatted lead notification to telesale team
        """
        message = f"""
🔔 <b>LEAD MỚI!</b>

👤 <b>Tên:</b> {customer_name}
📞 <b>SĐT:</b> <code>{customer_phone}</code>
📱 <b>Nguồn:</b> {source}

💬 <b>Tóm tắt:</b>
{summary or "Khách quan tâm sản phẩm"}

⏰ Hãy liên hệ ngay!
        """.strip()
        
        return await self.send_message(message)
    
    async def notify_error(
        self,
        error_type: str,
        details: str,
        user_id: str = ""
    ) -> bool:
        """
        Send error notification to admin
        """
        message = f"""
⚠️ <b>LỖI HỆ THỐNG</b>

❌ <b>Loại:</b> {error_type}
👤 <b>User:</b> {user_id or "N/A"}

📝 <b>Chi tiết:</b>
<code>{details[:500]}</code>
        """.strip()
        
        return await self.send_message(message)


# Global instance
telegram_notifier = TelegramNotifier()
