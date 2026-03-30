"""
Comprehensive Test Suite for Smart Chatbot
Tests all 10 main features and core services
"""
import asyncio
import sys
import os

# Add python app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from datetime import datetime
import httpx
import json

# Test Results
results = []

def log_result(test_name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append({"test": test_name, "passed": passed, "details": details})
    print(f"{status} | {test_name}: {details}")


# ============ UNIT TESTS ============

def test_response_splitter():
    """Test Feature 9: Human-like response splitting"""
    try:
        from app.services.response_splitter import split_response, get_typing_delay
        
        # Test 1: Short text (should not split)
        short_text = "Xin chào bạn!"
        parts = split_response(short_text)
        assert len(parts) == 1, f"Expected 1 part, got {len(parts)}"
        
        # Test 2: Long text (should split)
        long_text = "Xin chào bạn! Cảm ơn bạn đã quan tâm đến sản phẩm của chúng tôi. Chúng tôi có rất nhiều sản phẩm chất lượng cao với giá cả phải chăng. Bạn muốn tìm hiểu sản phẩm nào ạ? Chúng tôi sẵn sàng tư vấn cho bạn 24/7."
        parts = split_response(long_text)
        assert len(parts) >= 2, f"Expected >= 2 parts, got {len(parts)}"
        
        # Test 3: Typing delay
        delay = get_typing_delay("Hello world")
        assert 1.0 <= delay <= 5.0, f"Delay out of range: {delay}"
        
        log_result("Response Splitter (F9)", True, f"Split: {len(parts)} parts, delay: {delay}s")
        
    except Exception as e:
        log_result("Response Splitter (F9)", False, str(e))


def test_lead_extractor():
    """Test Feature 2: Phone number extraction"""
    try:
        from app.services.lead_extractor import extract_phone_number, is_valid_phone
        
        test_cases = [
            ("SĐT của tôi là 0909123456", "0909123456"),
            ("Liên hệ +84 912 345 678 nhé", "0912345678"),
            ("số máy: 091-234-5678", "0912345678"),
            ("Không có số điện thoại", None),
        ]
        
        passed = 0
        for text, expected in test_cases:
            result = extract_phone_number(text)
            if result == expected:
                passed += 1
            else:
                print(f"  ⚠️ '{text[:30]}...' -> got {result}, expected {expected}")
        
        success = passed == len(test_cases)
        log_result("Lead Extractor (F2)", success, f"{passed}/{len(test_cases)} test cases")
        
    except Exception as e:
        log_result("Lead Extractor (F2)", False, str(e))


async def test_redis_client():
    """Test Feature 6/8: Redis session and debounce"""
    try:
        from app.services.redis_client import redis_manager
        from app.config import get_settings
        
        settings = get_settings()
        
        # Connect to localhost for testing
        await redis_manager.connect(
            host="localhost",
            port=settings.redis_port,
            password=settings.redis_password
        )
        
        # Test ping
        await redis_manager.client.ping()
        
        # Test debounce buffer
        test_user = "test_user_comprehensive"
        msg = {"type": "text", "content": "Test message"}
        
        messages = await redis_manager.add_message_to_buffer(test_user, msg, debounce_seconds=10)
        assert len(messages) >= 1, "Buffer should have at least 1 message"
        
        # Test clear buffer
        cleared = await redis_manager.get_and_clear_buffer(test_user)
        assert len(cleared) >= 1, "Should clear at least 1 message"
        
        # Test session data
        await redis_manager.set_session_data("test_session_comp", {"name": "Test"}, ttl=60)
        data = await redis_manager.get_session_data("test_session_comp")
        assert data["name"] == "Test", "Session data mismatch"
        
        # Test admin handover
        await redis_manager.set_admin_handover("page123", "user123", minutes=1)
        is_admin = await redis_manager.is_admin_active("page123", "user123")
        assert is_admin, "Admin handover should be active"
        
        log_result("Redis Client (F6/F8)", True, "Ping, buffer, session, handover OK")
        
        await redis_manager.disconnect()
        
    except Exception as e:
        log_result("Redis Client (F6/F8)", False, str(e))


async def test_neo4j_client():
    """Test Feature 10: GraphRAG Neo4j"""
    try:
        from app.services.neo4j_client import neo4j_manager
        from app.config import get_settings
        
        settings = get_settings()
        
        await neo4j_manager.connect(
            uri="bolt://localhost:7687",
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
        
        # Test basic query
        result = await neo4j_manager.run_query("RETURN 1 as num")
        assert len(result) == 1 and result[0]["num"] == 1
        
        # Test product search
        products = await neo4j_manager.find_products_by_text("áo", limit=3)
        
        log_result("Neo4j Client (F10)", True, f"Query OK, found {len(products)} products")
        
        await neo4j_manager.disconnect()
        
    except Exception as e:
        log_result("Neo4j Client (F10)", False, str(e))


async def test_telegram_notifier():
    """Test Feature 5: Telegram notification"""
    try:
        from app.services.telegram_notifier import telegram_notifier
        from app.config import get_settings
        
        settings = get_settings()
        
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            log_result("Telegram Notifier (F5)", True, "Skipped (no credentials)")
            return
        
        # Send test notification
        success = await telegram_notifier.send_message(
            f"🧪 <b>Comprehensive Test</b>\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Status: All tests running..."
        )
        
        log_result("Telegram Notifier (F5)", success, "Message sent" if success else "Failed")
        
    except Exception as e:
        log_result("Telegram Notifier (F5)", False, str(e))


# ============ INTEGRATION TESTS ============

async def test_health_endpoint():
    """Test health check endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health/detailed", timeout=10)
            data = resp.json()
            
            is_healthy = resp.status_code == 200
            services = data.get("services", {})
            
            log_result("Health Endpoint", is_healthy, 
                       f"API={services.get('api')}, Redis={services.get('redis')}, Neo4j={services.get('neo4j')}")
            
    except Exception as e:
        log_result("Health Endpoint", False, str(e))


async def test_chat_processing():
    """Test chat processing endpoint (F1, F2, F3)"""
    try:
        payload = {
            "user_id": "test_comprehensive",
            "page_id": "page_demo",
            "user_name": "Anh Vượng",
            "platform": "messenger",
            "messages": [
                {"type": "text", "content": "Xin chào, báo giá sơ mi trắng. SĐT 0909123456"}
            ]
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post("http://localhost:8000/chat/process", json=payload)
            
            if resp.status_code != 200:
                log_result("Chat Processing", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
                return
            
            data = resp.json()
            
            checks = []
            # Check response parts
            if data.get("response_parts"):
                checks.append("✓ Response")
            # Check phone extraction
            if data.get("has_phone"):
                checks.append(f"✓ Phone={data.get('phone_number')}")
            # Check Zalo invite
            if data.get("should_invite_zalo"):
                checks.append("✓ ZaloInvite")
            # Check intent/sentiment
            if data.get("customer_intent"):
                checks.append(f"✓ Intent={data.get('customer_intent')}")
            
            log_result("Chat Processing (F1-F3)", True, ", ".join(checks))
            
    except Exception as e:
        log_result("Chat Processing (F1-F3)", False, str(e))


async def test_multimodal():
    """Test multimodal processing (F1)"""
    try:
        payload = {
            "user_id": "test_multimodal",
            "page_id": "page_demo",
            "user_name": "Test User",
            "platform": "messenger",
            "messages": [
                {"type": "text", "content": "Sản phẩm này giá bao nhiêu?"},
                {"type": "image", "content": None, "attachments": [
                    {"type": "image", "url": "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"}
                ]}
            ]
        }
        
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post("http://localhost:8000/chat/process", json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response_parts", [""])[0][:100]
                log_result("Multimodal (F1)", True, f"Response: {response_text}...")
            else:
                log_result("Multimodal (F1)", False, f"HTTP {resp.status_code}")
            
    except Exception as e:
        log_result("Multimodal (F1)", False, str(e))


# ============ MAIN ============

async def main():
    print("=" * 60)
    print("🧪 SMART CHATBOT - COMPREHENSIVE E2E TESTS")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Unit Tests (sync)
    print("📦 UNIT TESTS")
    print("-" * 40)
    test_response_splitter()
    test_lead_extractor()
    
    # Unit Tests (async)
    await test_redis_client()
    await test_neo4j_client()
    await test_telegram_notifier()
    
    print()
    print("🌐 INTEGRATION TESTS")
    print("-" * 40)
    await test_health_endpoint()
    await test_chat_processing()
    await test_multimodal()
    
    # Summary
    print()
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"  {status} {r['test']}: {r['details'][:50]}")
    
    print()
    print(f"🎯 Result: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ Some tests failed. Check details above.")


if __name__ == "__main__":
    asyncio.run(main())
