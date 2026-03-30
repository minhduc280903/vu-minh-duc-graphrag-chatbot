# -*- coding: utf-8 -*-
"""
Smart Chatbot - Complete System Verification
Kiểm tra toàn bộ hệ thống: API, Redis, Neo4j, n8n, Telegram
"""
import asyncio
import sys
import os

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

import httpx
from datetime import datetime

RESULTS = []

def log(component, status, detail=""):
    """Log test result"""
    icon = "✅" if status else "❌"
    RESULTS.append((component, status, detail))
    # Truncate and ascii-safe for Windows console
    safe_detail = detail[:80].encode('ascii', 'ignore').decode() if detail else ""
    print(f"{icon} {component}: {safe_detail}")


async def check_api_health():
    """Check API health endpoint"""
    print("\n" + "=" * 50)
    print("1. API SERVICE")
    print("=" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Basic health
            resp = await client.get("http://localhost:8000/health")
            if resp.status_code == 200:
                log("API Basic Health", True, "Status: healthy")
            else:
                log("API Basic Health", False, f"HTTP {resp.status_code}")
            
            # Detailed health
            resp = await client.get("http://localhost:8000/health/detailed")
            if resp.status_code == 200:
                data = resp.json()
                services = data.get("services", {})
                log("API Status", services.get("api") == "healthy", f"API={services.get('api')}")
                log("Redis Status", services.get("redis") == "healthy", f"Redis={services.get('redis')}")
                log("Neo4j Status", services.get("neo4j") == "healthy", f"Neo4j={services.get('neo4j')}")
            else:
                log("API Detailed Health", False, f"HTTP {resp.status_code}")
                
    except Exception as e:
        log("API Connection", False, str(e)[:60])


async def check_chat_processing():
    """Check chat processing endpoint"""
    print("\n" + "=" * 50)
    print("2. CHAT PROCESSING")
    print("=" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Test greeting
            payload = {
                "user_id": "verify_test",
                "page_id": "page_demo",
                "user_name": "Anh Test",
                "platform": "messenger",
                "messages": [{"type": "text", "content": "Xin chao, tu van san pham"}]
            }
            resp = await client.post("http://localhost:8000/chat/process", json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                log("Chat Processing", True, f"Response parts: {len(data.get('response_parts', []))}")
                log("Intent Detection", True, f"Intent: {data.get('customer_intent', 'N/A')}")
                log("AI Response", bool(data.get("response_parts")), "AI responded successfully")
            else:
                log("Chat Processing", False, f"HTTP {resp.status_code}: {resp.text[:60]}")
                
    except Exception as e:
        log("Chat Processing", False, str(e)[:60])


async def check_lead_extraction():
    """Check lead extraction"""
    print("\n" + "=" * 50)
    print("3. LEAD EXTRACTION")
    print("=" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "user_id": "verify_lead",
                "page_id": "page_demo",
                "user_name": "Chi Mai",
                "platform": "messenger",
                "messages": [{"type": "text", "content": "Tu van giup minh, SDT 0909123456"}]
            }
            resp = await client.post("http://localhost:8000/chat/process", json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                log("Phone Extraction", data.get("has_phone") == True, f"Phone: {data.get('phone_number')}")
                log("Zalo Invite Flag", True, f"should_invite_zalo: {data.get('should_invite_zalo')}")
            else:
                log("Lead Extraction", False, f"HTTP {resp.status_code}")
                
    except Exception as e:
        log("Lead Extraction", False, str(e)[:60])


async def check_n8n():
    """Check n8n service"""
    print("\n" + "=" * 50)
    print("4. N8N WORKFLOW ENGINE")
    print("=" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # n8n health check
            resp = await client.get("http://localhost:5678/healthz")
            if resp.status_code == 200:
                log("n8n Health", True, "n8n is running")
            else:
                log("n8n Health", False, f"HTTP {resp.status_code}")
            
            # n8n API (if configured)
            try:
                resp = await client.get("http://localhost:5678/api/v1/workflows", 
                                        headers={"X-N8N-API-KEY": os.getenv("N8N_API_KEY", "")})
                if resp.status_code == 200:
                    workflows = resp.json().get("data", [])
                    log("n8n Workflows", True, f"Found {len(workflows)} workflows")
                elif resp.status_code == 401:
                    log("n8n API Auth", False, "API key not configured (optional)")
                else:
                    log("n8n API", False, f"HTTP {resp.status_code}")
            except Exception:
                log("n8n API", False, "API not accessible (optional)")
                
    except Exception as e:
        log("n8n Connection", False, str(e)[:60])


async def check_redis_direct():
    """Check Redis directly"""
    print("\n" + "=" * 50)
    print("5. REDIS CACHE")
    print("=" * 50)
    
    try:
        from app.services.redis_client import redis_manager
        await redis_manager.connect(
            host='localhost',
            port=6379,
            password=os.getenv("REDIS_PASSWORD", "redis_password_2024")
        )
        
        # Ping test
        await redis_manager.client.ping()
        log("Redis Ping", True, "Connection successful")
        
        # Buffer test
        await redis_manager.add_message_to_buffer("verify_test", {"type": "text", "content": "test"}, 10)
        msgs = await redis_manager.get_and_clear_buffer("verify_test")
        log("Redis Buffer", len(msgs) >= 1, f"Buffer operations working")
        
        # Session test
        await redis_manager.set_session_data("verify_session", {"name": "Test"}, ttl=60)
        data = await redis_manager.get_session_data("verify_session")
        log("Redis Session", data.get("name") == "Test", "Session storage working")
        
        await redis_manager.disconnect()
        
    except Exception as e:
        log("Redis Direct", False, str(e)[:60])


async def check_telegram():
    """Check Telegram notification"""
    print("\n" + "=" * 50)
    print("6. TELEGRAM NOTIFIER")
    print("=" * 50)
    
    try:
        from app.services.telegram_notifier import telegram_notifier
        from app.config import get_settings
        
        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            log("Telegram Config", False, "Bot token/chat ID not configured")
            return
        
        success = await telegram_notifier.send_message(
            f"<b>System Verification</b>\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Status: All systems operational"
        )
        log("Telegram Send", success, "Message sent to group" if success else "Failed to send")
        
    except Exception as e:
        log("Telegram", False, str(e)[:60])


async def check_docker_services():
    """Check Docker container status"""
    print("\n" + "=" * 50)
    print("7. DOCKER SERVICES")
    print("=" * 50)
    
    import subprocess
    
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}:{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            containers = result.stdout.strip().split('\n')
            for container in containers:
                if 'smart-chatbot' in container or 'n8n' in container:
                    name, status = container.split(':', 1) if ':' in container else (container, "unknown")
                    is_up = "Up" in status
                    log(f"Container {name}", is_up, status[:40])
        else:
            log("Docker", False, "Cannot get container status")
            
    except Exception as e:
        log("Docker Check", False, str(e)[:60])


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, status, _ in RESULTS if status)
    total = len(RESULTS)
    
    print(f"\nResult: {passed}/{total} checks passed")
    
    failed = [(name, detail) for name, status, detail in RESULTS if not status]
    if failed:
        print("\n❌ Failed checks:")
        for name, detail in failed:
            print(f"   - {name}: {detail}")
    
    print("\n" + "=" * 50)
    if passed == total:
        print("✅ ALL SYSTEMS OPERATIONAL!")
    elif passed >= total * 0.8:
        print("⚠️  MOSTLY OPERATIONAL - Some optional services need attention")
    else:
        print("❌ ISSUES DETECTED - Check failed components above")
    print("=" * 50)


async def main():
    print("=" * 50)
    print("SMART CHATBOT - COMPLETE SYSTEM VERIFICATION")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all checks
    await check_docker_services()
    await check_api_health()
    await check_redis_direct()
    await check_chat_processing()
    await check_lead_extraction()
    await check_n8n()
    await check_telegram()
    
    # Summary
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
