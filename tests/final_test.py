# -*- coding: utf-8 -*-
"""
Final E2E Test Script for Smart Chatbot
Tests integration endpoints via HTTP (Docker-based API)
"""
import asyncio
import sys
import os

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add python app to path for unit tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

import httpx
from datetime import datetime

results = []

def log(name, passed, detail=""):
    # Avoid duplicate logging
    for existing_name, _ in results:
        if existing_name == name:
            return
    results.append((name, passed))
    status = "PASS" if passed else "FAIL"
    # Truncate detail to avoid encoding issues
    safe_detail = detail[:100].encode('ascii', 'ignore').decode() if detail else ""
    print(f"[{status}] {name}: {safe_detail}")


# ============ UNIT TESTS ============

def test_unit_response_splitter():
    print("\n== UNIT TESTS ==")
    print("-" * 40)
    try:
        from app.services.response_splitter import split_response, get_typing_delay
        short = split_response("Hello!")
        long_text = "A" * 300
        long = split_response(long_text)
        delay = get_typing_delay("Hello world")
        success = len(short) == 1 and len(long) >= 2 and 1 <= delay <= 5
        log("Response Splitter (F9)", success, f"Short={len(short)}, Long={len(long)}, Delay={delay}s")
    except Exception as e:
        log("Response Splitter (F9)", False, str(e)[:80])


def test_unit_lead_extractor():
    try:
        from app.services.lead_extractor import extract_phone_number
        tests = [
            ("SDT 0909123456", "0909123456"),
            ("+84 912 345 678", "0912345678"),
            ("No phone here", None),
        ]
        passed = sum(1 for t, exp in tests if extract_phone_number(t) == exp)
        log("Lead Extractor (F2)", passed == len(tests), f"{passed}/{len(tests)} test cases")
    except Exception as e:
        log("Lead Extractor (F2)", False, str(e)[:80])


async def test_unit_redis():
    try:
        from app.services.redis_client import redis_manager
        await redis_manager.connect(host='localhost', port=6379, password='redis_password_2024')
        await redis_manager.client.ping()
        
        # Test buffer
        await redis_manager.add_message_to_buffer('test_final', {'type': 'text', 'content': 'OK'}, 10)
        msgs = await redis_manager.get_and_clear_buffer('test_final')
        
        # Test session
        await redis_manager.set_session_data('test_final', {'name': 'Test'}, ttl=60)
        data = await redis_manager.get_session_data('test_final')
        
        await redis_manager.disconnect()
        log("Redis Client (F6/F8)", len(msgs) >= 1 and data.get('name') == 'Test',
            f"Buffer={len(msgs)}, Session OK")
    except Exception as e:
        log("Redis Client (F6/F8)", False, str(e)[:80])


# ============ INTEGRATION TESTS (via HTTP to Docker API) ============

async def test_health():
    print("\n== INTEGRATION TESTS (via Docker API) ==")
    print("-" * 40)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get('http://localhost:8000/health/detailed', timeout=10)
            data = resp.json()
            services = data.get("services", {})
            log("Health Endpoint", resp.status_code == 200,
                f"API={services.get('api')}, Redis={services.get('redis')}, Neo4j={services.get('neo4j')}")
    except Exception as e:
        log("Health Endpoint", False, str(e)[:80])


async def test_telegram():
    try:
        from app.services.telegram_notifier import telegram_notifier
        success = await telegram_notifier.send_message(
            f"<b>Smart Chatbot E2E Test</b>\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Status: Tests completed!"
        )
        log("Telegram Notifier (F5)", success, "Message sent" if success else "Not configured")
    except Exception as e:
        log("Telegram Notifier (F5)", False, str(e)[:80])


async def test_chat_greeting():
    try:
        payload = {
            "user_id": "test_greeting",
            "page_id": "page_demo",
            "user_name": "Anh Vuong",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Xin chao, minh muon tim hieu san pham"}]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('http://localhost:8000/chat/process', json=payload)
            if resp.status_code == 200:
                data = resp.json()
                response_text = (data.get("response_parts", [""])[0][:50])
                log("Chat Greeting (F2)", True, f"Got response with {len(data.get('response_parts', []))} parts")
            else:
                log("Chat Greeting (F2)", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log("Chat Greeting (F2)", False, str(e)[:80])


async def test_lead_generation():
    try:
        payload = {
            "user_id": "test_lead",
            "page_id": "page_demo",
            "user_name": "Anh Vuong",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Tu van giup minh, SDT 0909123456 nhe"}]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('http://localhost:8000/chat/process', json=payload)
            if resp.status_code == 200:
                data = resp.json()
                has_phone = data.get("has_phone")
                phone = data.get("phone_number")
                zalo = data.get("should_invite_zalo")
                log("Lead Generation (F2/F7)", has_phone and phone == "0909123456",
                    f"Phone={phone}, ZaloInvite={zalo}")
            else:
                log("Lead Generation (F2/F7)", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log("Lead Generation (F2/F7)", False, str(e)[:80])


async def test_product_query():
    try:
        payload = {
            "user_id": "test_product",
            "page_id": "page_demo",
            "user_name": "Anh Vuong",
            "platform": "messenger",
            "messages": [{"type": "text", "content": "Bao gia ao so mi trang"}]
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post('http://localhost:8000/chat/process', json=payload)
            if resp.status_code == 200:
                data = resp.json()
                intent = data.get("customer_intent")
                log("Product Query (F10)", True, f"Intent={intent}, Response received")
            else:
                log("Product Query (F10)", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log("Product Query (F10)", False, str(e)[:80])


async def test_multimodal():
    print("\n== MULTIMODAL TEST (F1) ==")
    print("-" * 40)
    try:
        payload = {
            "user_id": "test_multimodal",
            "page_id": "page_demo",
            "user_name": "Test User",
            "platform": "messenger",
            "messages": [
                {"type": "text", "content": "What is this?"},
                {"type": "image", "content": None, "attachments": [
                    {"type": "image", "url": "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"}
                ]}
            ]
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post('http://localhost:8000/chat/process', json=payload)
            if resp.status_code == 200:
                data = resp.json()
                log("Multimodal Image (F1)", True, f"Response received with {len(data.get('response_parts', []))} parts")
            else:
                log("Multimodal Image (F1)", False, f"HTTP {resp.status_code}")
    except Exception as e:
        log("Multimodal Image (F1)", False, str(e)[:80])


async def main():
    print("=" * 50)
    print("SMART CHATBOT - COMPREHENSIVE E2E TESTS")
    print("=" * 50)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Unit tests
    test_unit_response_splitter()
    test_unit_lead_extractor()
    await test_unit_redis()
    
    # Integration tests
    await test_health()
    await test_telegram()
    await test_chat_greeting()
    await test_lead_generation()
    await test_product_query()
    await test_multimodal()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, p in results:
        status = "PASS" if p else "FAIL"
        print(f"  [{status}] {name}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 50)
    
    if passed == total:
        print("ALL TESTS PASSED!")
    elif passed >= total * 0.7:
        print("MOSTLY PASSED - Some tests may need local dependencies")
    else:
        print("Some tests failed. Check details above.")
    
    return passed, total


if __name__ == "__main__":
    asyncio.run(main())
