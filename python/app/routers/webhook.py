"""
Webhook Router
Handles incoming webhooks from Facebook Messenger and Zalo
"""
import hmac
import hashlib
from typing import Any

from fastapi import APIRouter, Request, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import get_settings
from app.services.redis_client import redis_manager
from app.services.debouncer import debounce_processor
from app.services.rate_limiter import user_rate_limiter

router = APIRouter()


def verify_fb_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """
    Verify that the webhook request came from Facebook
    https://developers.facebook.com/docs/messenger-platform/webhooks#verify-requests
    """
    if not signature or not app_secret:
        return False
    
    try:
        expected = "sha256=" + hmac.new(
            app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


# ============ Facebook Messenger Webhook ============

@router.get("/messenger")
async def verify_messenger_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Facebook Webhook Verification
    Called when you set up the webhook in Facebook Developer Portal
    """
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.fb_verify_token:
        logger.info("✅ Facebook webhook verified")
        # BẮT BUỘC: Trả về hub.challenge dưới dạng Plain Text string
        # Facebook yêu cầu response phải là text/plain, không phải JSON
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(f"❌ Webhook verification failed: {hub_verify_token}")
    return JSONResponse(status_code=403, content={"error": "Verification failed"})


@router.post("/messenger")
async def receive_messenger_webhook(request: Request):
    """
    Receive messages from Facebook Messenger
    Handles text, image, audio, and other attachments
    """
    settings = get_settings()
    
    # Get raw body for signature verification
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    # Verify signature (skip in dev if no app_secret)
    if settings.fb_app_secret:
        if not verify_fb_signature(body_bytes, signature, settings.fb_app_secret):
            logger.warning("❌ Invalid Facebook signature")
            raise HTTPException(status_code=403, detail="Invalid signature")
    
    body = await request.json()
    logger.debug(f"Received webhook: {body}")
    
    # Extract messages from webhook payload
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            page_id = entry.get("id")
            
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                recipient_id = messaging_event.get("recipient", {}).get("id")
                timestamp = messaging_event.get("timestamp")
                
                # Check if this is from any admin (support multiple admins)
                admin_list = settings.get_admin_list()
                if sender_id in admin_list:
                    # Admin is responding - set handover flag
                    await redis_manager.set_admin_handover(
                        page_id=page_id,
                        user_id=recipient_id,  # The customer being replied to
                        minutes=settings.admin_handover_minutes
                    )
                    logger.info(f"🧑‍💼 Admin takeover detected for {recipient_id} by {sender_id}")
                    return {"status": "admin_handover"}
                
                # Check if admin is currently handling this conversation
                if await redis_manager.is_admin_active(page_id, sender_id):
                    logger.info(f"⏸️ Bot paused - admin is active for {sender_id}")
                    return {"status": "paused_for_admin"}

                # Rate limit check per user
                rate_check = await user_rate_limiter.check_rate_limit(sender_id, page_id)
                if not rate_check["allowed"]:
                    logger.warning(f"🚫 Rate limited: {sender_id} - {rate_check['reason']}")
                    return {"status": "rate_limited", "reset_at": rate_check["reset_at"]}

                # Process message
                message = messaging_event.get("message", {})
                message_id = message.get("mid")  # Facebook message ID

                if message:
                    # Idempotency check - prevent duplicate processing
                    if message_id:
                        if await redis_manager.is_message_processed(message_id):
                            logger.debug(f"⏭️ Message {message_id} already processed, skipping")
                            return {"status": "duplicate"}
                        await redis_manager.mark_message_processed(message_id)

                    # Extract message content
                    msg_data = {
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "timestamp": timestamp,
                        "type": "text",
                        "content": None,
                        "attachments": []
                    }
                    
                    # Text message
                    if "text" in message:
                        msg_data["type"] = "text"
                        msg_data["content"] = message["text"]
                    
                    # Attachments (image, audio, video, file)
                    if "attachments" in message:
                        for attachment in message["attachments"]:
                            att_type = attachment.get("type")
                            payload = attachment.get("payload", {})
                            
                            msg_data["attachments"].append({
                                "type": att_type,
                                "url": payload.get("url"),
                                "sticker_id": payload.get("sticker_id")
                            })
                        
                        # Set primary type based on first attachment
                        if msg_data["attachments"]:
                            msg_data["type"] = msg_data["attachments"][0]["type"]
                    
                    # Add to debounce buffer
                    await debounce_processor.add_message(
                        user_id=sender_id,
                        page_id=page_id,
                        message=msg_data
                    )
                    
                    logger.info(f"📨 Message buffered from {sender_id}: {msg_data['type']}")
    
    return {"status": "received"}


# ============ Zalo OA Webhook ============

@router.post("/zalo")
async def receive_zalo_webhook(request: Request):
    """
    Receive messages from Zalo OA
    Similar structure to Messenger but with Zalo-specific fields
    """
    settings = get_settings()  # Get settings inside function
    body = await request.json()
    logger.debug(f"Received Zalo webhook: {body}")
    
    event_name = body.get("event_name")
    
    if event_name == "user_send_text":
        # Text message
        sender_id = body.get("sender", {}).get("id")
        message = body.get("message", {}).get("text", "")
        
        msg_data = {
            "sender_id": sender_id,
            "page_id": settings.zalo_oa_id,
            "platform": "zalo",
            "type": "text",
            "content": message
        }
        
        await debounce_processor.add_message(
            user_id=sender_id,
            page_id=settings.zalo_oa_id,
            message=msg_data
        )
        
    elif event_name == "user_send_image":
        # Image message
        sender_id = body.get("sender", {}).get("id")
        image_url = body.get("message", {}).get("url")
        
        msg_data = {
            "sender_id": sender_id,
            "page_id": settings.zalo_oa_id,
            "platform": "zalo",
            "type": "image",
            "content": image_url,
            "attachments": [{"type": "image", "url": image_url}]
        }
        
        await debounce_processor.add_message(
            user_id=sender_id,
            page_id=settings.zalo_oa_id,
            message=msg_data
        )
    
    return {"status": "received"}
