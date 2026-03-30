"""
Smart Chatbot - FastAPI Application Entry Point
Main orchestration for the hybrid AI chatbot system
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.routers import webhook, chat, health
from app.services.redis_client import redis_manager
from app.services.neo4j_client import neo4j_manager
from app.services.init_db import init_neo4j_schema, generate_product_embeddings
from app.services.logging_config import setup_logging, CorrelationIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events"""
    settings = get_settings()

    # Setup structured logging first
    setup_logging(json_logs=False)  # Set to True in production

    # Startup
    logger.info("🚀 Starting Smart Chatbot API...")
    
    # Initialize Redis
    await redis_manager.connect(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password
    )
    logger.info("✅ Redis connected")
    
    # Initialize Neo4j
    await neo4j_manager.connect(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password
    )
    logger.info("✅ Neo4j connected")

    # Auto-seed Neo4j schema and sample data
    try:
        await init_neo4j_schema()
        await generate_product_embeddings()
    except Exception as e:
        logger.warning(f"⚠️ Neo4j schema init warning: {e}")

    logger.info("🤖 Smart Chatbot API ready!")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Smart Chatbot API...")
    await redis_manager.disconnect()
    await neo4j_manager.disconnect()
    logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="Smart Chatbot API",
    description="Hybrid AI Chatbot with n8n + Python for Facebook Messenger & Zalo",
    version="1.0.0",
    lifespan=lifespan
)

# ============ Rate Limiting (Production Security) ============
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("✅ Rate limiting enabled")
except ImportError:
    logger.warning("⚠️ slowapi not installed, rate limiting disabled")
    limiter = None

# ============ CORS Security ============
# Restricted to n8n and internal services only
# In production, replace with your actual n8n domain
allowed_origins = [
    "http://localhost:5678",      # n8n local development
    "http://n8n:5678",            # n8n in Docker network
    "https://your-n8n-domain.com" # Replace with production domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restricted, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only methods needed
    allow_headers=["*"],
)

# ============ Correlation ID Middleware ============
# Must be added AFTER CORS middleware for proper ordering
app.add_middleware(CorrelationIDMiddleware)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Smart Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }
