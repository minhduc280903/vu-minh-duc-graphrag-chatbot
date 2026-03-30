
import asyncio
import httpx
import json
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Test Data
USER_ID = "test_user_vip"
PAGE_ID = "page_demo"

async def test_health():
    print("\n[1] Testing System Health...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_URL}/health/detailed")
            data = resp.json()
            print(f"✅ API Status: {data['status']}")
            print(f"   Services: {json.dumps(data.get('services', {}), indent=2)}")
            return data['status'] == 'healthy'
        except Exception as e:
            print(f"❌ Health Check Failed: {e}")
            return False

async def test_chat_scenario(name, messages, expected_checks):
    print(f"\n[{name}] Testing Scenario...")
    
    payload = {
        "user_id": USER_ID,
        "page_id": PAGE_ID,
        "user_name": "Anh Vượng",
        "platform": "messenger",
        "messages": messages
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            start_time = datetime.now()
            resp = await client.post(f"{API_URL}/chat/process", json=payload)
            duration = (datetime.now() - start_time).total_seconds()
            
            if resp.status_code != 200:
                print(f"❌ Failed: {resp.status_code} - {resp.text}")
                return False
                
            data = resp.json()
            print(f"✅ Response ({duration:.2f}s):")
            print(f"   AI Text: {data['response_parts'][0][:100]}...")
            
            # Verify checks
            all_passed = True
            for check, expected in expected_checks.items():
                actual = data.get(check)
                if actual == expected:
                    print(f"   ✅ Check {check}={expected} Passed")
                else:
                    print(f"   ❌ Check {check}={expected} Failed (Got {actual})")
                    all_passed = False
            
            return all_passed
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

async def main():
    print("🚀 STARTING COMPREHENSIVE SYSTEM TEST")
    print("=====================================")
    
    # 1. Health Check
    if not await test_health():
        print("❌ System not healthy, aborting.")
        return

    # Scenario 1: Greeting & Personalization
    # Expect: Friendly response using name
    await test_chat_scenario(
        "2. Greeting",
        [{"type": "text", "content": "Xin chào, mình muốn tìm hiểu sản phẩm"}],
        {"has_phone": False, "should_invite_zalo": False}
    )

    # Scenario 2: Lead Generation (Phone Number)
    # Expect: has_phone=True, should_invite_zalo=True, Telegram Notification (internal)
    await test_chat_scenario(
        "3. Lead Gen",
        [{"type": "text", "content": "Tư vấn giúp mình, sđt 0909123456 nhé"}],
        {"has_phone": True, "should_invite_zalo": True, "phone_number": "0909123456"}
    )

    # Scenario 3: Product Inquiry (Pricing/Details)
    # Expect: AI response about product (GraphRAG)
    # Note: Requires product data in Neo4j. If empty, AI might hallucinate or say no info.
    # We check if it responds gracefully.
    await test_chat_scenario(
        "4. Product Query",
        [{"type": "text", "content": "Báo giá cho mình sản phẩm sơ mi trắng"}],
        {"has_phone": False}
    )

    # Scenario 4: Multimodal (Simulated Image)
    # Expect: AI acknowledges image content
    await test_chat_scenario(
        "5. Image Analysis",
        [
            {"type": "text", "content": "Cái này giá bao nhiêu?"},
            {"type": "image", "content": None, "attachments": [{"type": "image", "url": "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"}]}
        ],
        {"has_phone": False}
    )
    
    print("\n=====================================")
    print("🏁 TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(main())
