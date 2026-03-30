# -*- coding: utf-8 -*-
"""
Smart Chatbot - Pytest Configuration and Fixtures
Provides shared fixtures for all test modules
"""
import asyncio
import os
import sys
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

# Add python app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

# ============ Pytest Configuration ============

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============ Environment Fixtures ============

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")
    os.environ.setdefault("REDIS_PASSWORD", "redis_password_2024")
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "neo4j_password_2024")
    os.environ.setdefault("GOOGLE_API_KEY", "test_key")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
    os.environ.setdefault("TELEGRAM_CHAT_ID", "")
    yield


# ============ Redis Fixtures ============

@pytest.fixture
async def redis_client():
    """Real Redis client for integration tests"""
    from app.services.redis_client import redis_manager
    try:
        await redis_manager.connect(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD", "")
        )
        yield redis_manager
        await redis_manager.disconnect()
    except Exception:
        pytest.skip("Redis not available")


@pytest.fixture
def mock_redis():
    """Mocked Redis client for unit tests"""
    mock = MagicMock()
    mock.client = AsyncMock()
    mock.client.ping = AsyncMock(return_value=True)
    mock.client.get = AsyncMock(return_value=None)
    mock.client.set = AsyncMock(return_value=True)
    mock.client.setex = AsyncMock(return_value=True)
    mock.client.delete = AsyncMock(return_value=1)
    mock.client.rpush = AsyncMock(return_value=1)
    mock.client.lrange = AsyncMock(return_value=[])
    mock.client.expire = AsyncMock(return_value=True)
    mock.client.exists = AsyncMock(return_value=0)
    mock.client.incr = AsyncMock(return_value=1)
    mock.client.ttl = AsyncMock(return_value=60)
    mock.client.hset = AsyncMock(return_value=1)
    mock.client.hgetall = AsyncMock(return_value={})
    mock.client.hdel = AsyncMock(return_value=1)
    return mock


# ============ Neo4j Fixtures ============

@pytest.fixture
async def neo4j_client():
    """Real Neo4j client for integration tests"""
    from app.services.neo4j_client import neo4j_manager
    try:
        await neo4j_manager.connect(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "")
        )
        yield neo4j_manager
        await neo4j_manager.disconnect()
    except Exception:
        pytest.skip("Neo4j not available")


@pytest.fixture
def mock_neo4j():
    """Mocked Neo4j client for unit tests"""
    mock = MagicMock()
    mock.driver = MagicMock()
    mock.run_query = AsyncMock(return_value=[{"num": 1}])
    mock.find_products_by_text = AsyncMock(return_value=[])
    mock.find_products_by_vector = AsyncMock(return_value=[])
    mock.get_product_full_context = AsyncMock(return_value={})
    mock.answer_question_with_graph = AsyncMock(return_value={})
    return mock


# ============ HTTP Client Fixtures ============

@pytest.fixture
def api_base_url():
    """Base URL for API tests"""
    return os.getenv("API_URL", "http://localhost:8000")


@pytest.fixture
async def async_client(api_base_url) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for API tests"""
    async with httpx.AsyncClient(base_url=api_base_url, timeout=60) as client:
        yield client


# ============ AI/LLM Mock Fixtures ============

@pytest.fixture
def mock_gemini():
    """Mocked Gemini client for unit tests"""
    mock = MagicMock()
    mock.models = MagicMock()
    mock.models.generate_content = AsyncMock(return_value=MagicMock(
        text="Xin chào! Tôi là chatbot thông minh.",
        candidates=[MagicMock(content=MagicMock(parts=[MagicMock(text="Hello")]))]
    ))
    return mock


@pytest.fixture
def mock_ai_brain():
    """Mocked AI Brain for unit tests"""
    from app.services.ai_brain import AIResponse
    mock = MagicMock()
    mock.process = AsyncMock(return_value=AIResponse(
        text="Xin chào bạn! Tôi có thể giúp gì cho bạn?",
        response_parts=["Xin chào bạn!", "Tôi có thể giúp gì cho bạn?"],
        has_products=False,
        products=[],
        entities=["sản phẩm"],
        confidence=0.9
    ))
    return mock


# ============ Telegram Mock Fixtures ============

@pytest.fixture
def mock_telegram():
    """Mocked Telegram client for unit tests"""
    mock = MagicMock()
    mock.send_message = AsyncMock(return_value=True)
    mock.notify_new_lead = AsyncMock(return_value=True)
    mock.notify_error = AsyncMock(return_value=True)
    return mock


# ============ Messenger API Mock Fixtures ============

@pytest.fixture
def mock_messenger_api():
    """Mocked Messenger API for unit tests"""
    mock = MagicMock()
    mock.send_text = AsyncMock(return_value=True)
    mock.send_image = AsyncMock(return_value=True)
    mock.send_typing_on = AsyncMock(return_value=True)
    mock.send_typing_off = AsyncMock(return_value=True)
    mock.get_user_profile = AsyncMock(return_value={"first_name": "Test", "last_name": "User"})
    return mock


# ============ Test Data Fixtures ============

@pytest.fixture
def sample_chat_message():
    """Sample chat message for testing"""
    return {
        "user_id": "test_user_001",
        "page_id": "page_demo",
        "user_name": "Anh Vượng",
        "platform": "messenger",
        "messages": [
            {"type": "text", "content": "Xin chào, tôi muốn tìm hiểu sản phẩm"}
        ]
    }


@pytest.fixture
def sample_lead_message():
    """Sample message with phone number"""
    return {
        "user_id": "test_user_002",
        "page_id": "page_demo",
        "user_name": "Chị Mai",
        "platform": "messenger",
        "messages": [
            {"type": "text", "content": "Tư vấn giúp mình, SĐT 0909123456"}
        ]
    }


@pytest.fixture
def sample_multimodal_message():
    """Sample multimodal message with image"""
    return {
        "user_id": "test_user_003",
        "page_id": "page_demo",
        "user_name": "Test User",
        "platform": "messenger",
        "messages": [
            {"type": "text", "content": "Sản phẩm này giá bao nhiêu?"},
            {
                "type": "image",
                "content": None,
                "attachments": [{
                    "type": "image",
                    "url": "https://storage.googleapis.com/generativeai-downloads/images/scones.jpg"
                }]
            }
        ]
    }


@pytest.fixture
def sample_products():
    """Sample product data for testing"""
    return [
        {
            "id": "prod_001",
            "name": "Áo sơ mi trắng",
            "price": 350000,
            "description": "Áo sơ mi nam cao cấp",
            "image_url": "https://example.com/shirt.jpg"
        },
        {
            "id": "prod_002",
            "name": "Quần tây đen",
            "price": 450000,
            "description": "Quần tây nam công sở",
            "image_url": "https://example.com/pants.jpg"
        }
    ]


# ============ Phone Number Test Data ============

@pytest.fixture
def phone_test_cases():
    """Test cases for phone number extraction"""
    return [
        # (input_text, expected_normalized_phone)
        ("SĐT của tôi là 0909123456", "0909123456"),
        ("Liên hệ +84 912 345 678 nhé", "0912345678"),
        ("số máy: 091-234-5678", "0912345678"),
        ("Call me at 084.912.345.678", "0912345678"),
        ("Điện thoại (090) 123 4567", "0901234567"),
        ("Không có số điện thoại", None),
        ("Số này 12345 không hợp lệ", None),
        ("Zalo 0909888777 nhé", "0909888777"),
    ]


# ============ Response Splitter Test Data ============

@pytest.fixture
def long_response_text():
    """Long text for response splitter testing"""
    return """
Xin chào bạn! Cảm ơn bạn đã quan tâm đến sản phẩm của chúng tôi. 
Chúng tôi có rất nhiều sản phẩm chất lượng cao với giá cả phải chăng. 
Bạn muốn tìm hiểu sản phẩm nào ạ? 
Chúng tôi sẵn sàng tư vấn cho bạn 24/7.
Bạn có thể cho mình biết thêm về nhu cầu của bạn được không?
Chúng tôi sẽ tư vấn sản phẩm phù hợp nhất cho bạn.
""".strip()
