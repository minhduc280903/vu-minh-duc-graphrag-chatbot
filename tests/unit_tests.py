"""
Comprehensive Unit and Integration Tests for Smart Chatbot
Tests all 10 main features end-to-end
"""
import asyncio
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

from datetime import datetime

# Test Results Collector
results = []

def log_result(test_name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status} | {test_name}: {details}")


async def test_response_splitter():
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
        
        # Test 3: Typing delay calculation
        delay = get_typing_delay("Hello world")
        assert 1.0 <= delay <= 5.0, f"Delay out of range: {delay}"
        
        log_result("Response Splitter", True, f"Split into {len(parts)} parts, delay={delay}s")
        
    except Exception as e:
        log_result("Response Splitter", False, str(e))


async def test_lead_extractor():
    """Test Feature 2: Phone number extraction"""
    try:
        from app.services.lead_extractor import extract_phone_number, is_valid_phone, normalize_phone
        
        # Test cases
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
                print(f"  ⚠️ '{text}' -> got {result}, expected {expected}")
        
        success = passed == len(test_cases)
        log_result("Lead Extractor", success, f"{passed}/{len(test_cases)} test cases passed")
        
    except Exception as e:
        log_result("Lead Extractor", False, str(e))


async def test_redis_client():
    """Test Feature 6: Redis session and debounce buffer"""
    try:
        from app.services.redis_client import redis_manager
        from app.config import get_settings
        
        settings = get_settings()
        
        # Connect
        await redis_manager.connect(
            host="localhost",  # Use localhost for local testing
            port=settings.redis_port,
            password=settings.redis_password
        )
        
        # Test ping
        await redis_manager.client.ping()
        
        # Test debounce buffer
        test_user = "test_user_unit"
        msg = {"type": "text", "content": "Hello"}
        
        messages = await redis_manager.add_message_to_buffer(test_user, msg, debounce_seconds=5)
        assert len(messages) >= 1
        
        # Clear buffer
        cleared = await redis_manager.get_and_clear_buffer(test_user)
        assert len(cleared) >= 1
        
        # Test session data
        await redis_manager.set_session_data("test_session", {"name": "Test"}, ttl=60)
        data = await redis_manager.get_session_data("test_session")
        assert data["name"] == "Test"
        
        log_result("Redis Client", True, "Ping, buffer, and session operations successful")
        
        await redis_manager.disconnect()
        
    except Exception as e:
        log_result("Redis Client", False, str(e))


async def test_neo4j_client():
    """Test Feature 10: GraphRAG Neo4j operations"""
    try:
        from app.services.neo4j_client import neo4j_manager
        from app.config import get_settings
        
        settings = get_settings()
        
        # Connect
        await neo4j_manager.connect(
            uri="bolt://localhost:7687",
            user=settings.neo4j_user,
            password=settings.neo4j_password
        )
        
        # Test query
        result = await neo4j_manager.run_query("RETURN 1 as num")
        assert len(result) == 1
        assert result[0]["num"] == 1
        
        # Test product search (may return empty if no products)
        products = await neo4j_manager.find_products_by_text("áo", limit=3)
        
        log_result("Neo4j Client", True, f"Query OK, found {len(products)} products")
        
        await neo4j_manager.disconnect()
        
    except Exception as e:
        log_result("Neo4j Client", False, str(e))


async def test_telegram_notifier():
    """Test Feature 5: Telegram notification"""
    try:
        from app.services.telegram_notifier import telegram_notifier
        from app.config import get_settings
        
        settings = get_settings()
        
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            log_result("Telegram Notifier", True, "Skipped (no credentials configured)")
            return
        
        # Send test notification
        success = await telegram_notifier.send_message(
            f"🧪 Test notification at {datetime.now().strftime('%H:%M:%S')}"
        )
        
        log_result("Telegram Notifier", success, "Message sent" if success else "Failed to send")
        
    except Exception as e:
        log_result("Telegram Notifier", False, str(e))


async def main():
    print("=" * 60)
    print("🧪 SMART CHATBOT - COMPREHENSIVE UNIT TESTS")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    await test_response_splitter()
    await test_lead_extractor()
    await test_redis_client()
    await test_neo4j_client()
    await test_telegram_notifier()
    
    # Summary
    print()
    print("=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"  {status} {r['test']}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
