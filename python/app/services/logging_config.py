"""
Logging Configuration with Correlation ID
Structured logging for better debugging and monitoring
"""
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

from loguru import logger
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to store request-specific data
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def get_request_id() -> str:
    """Get current request ID from context"""
    return request_id_ctx.get() or "no-request-id"


def get_user_id() -> str:
    """Get current user ID from context"""
    return user_id_ctx.get() or "anonymous"


def set_context(request_id: str, user_id: Optional[str] = None):
    """Set logging context for current request"""
    request_id_ctx.set(request_id)
    if user_id:
        user_id_ctx.set(user_id)


def clear_context():
    """Clear logging context after request"""
    request_id_ctx.set(None)
    user_id_ctx.set(None)


def log_format(record):
    """Custom log format with correlation ID"""
    request_id = get_request_id()
    user_id = get_user_id()

    # Add context to extra
    record["extra"]["request_id"] = request_id
    record["extra"]["user_id"] = user_id

    # Format string
    base_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>rid:{extra[request_id]}</cyan> | "
    )

    # Add user_id only if not anonymous
    if user_id != "anonymous":
        base_format += "<yellow>uid:{extra[user_id]}</yellow> | "

    base_format += "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>\n"

    return base_format


def setup_logging(json_logs: bool = False):
    """
    Configure loguru for structured logging

    Args:
        json_logs: If True, output JSON format (for production/log aggregation)
    """
    # Remove default handler
    logger.remove()

    if json_logs:
        # JSON format for production (ELK, CloudWatch, etc.)
        logger.add(
            sys.stdout,
            format="{message}",
            serialize=True,  # Output as JSON
            level="INFO"
        )
    else:
        # Pretty format for development
        logger.add(
            sys.stdout,
            format=log_format,
            level="DEBUG",
            colorize=True
        )

    # File logging with rotation
    logger.add(
        "logs/chatbot_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotate at midnight
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | rid:{extra[request_id]} | uid:{extra[user_id]} | {name}:{function}:{line} - {message}",
        level="INFO"
    )

    logger.info("📝 Logging configured")


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation ID to every request

    Flow:
    1. Check for X-Request-ID header (from n8n or upstream)
    2. Generate new UUID if not present
    3. Set context for logging
    4. Add X-Request-ID to response headers
    """

    async def dispatch(self, request: Request, call_next):
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())[:8]  # Short UUID for readability

        # Try to extract user_id from request body or query
        user_id = None
        if request.method == "POST":
            try:
                # Peek at body without consuming it
                body = await request.body()
                import json
                data = json.loads(body)
                user_id = data.get("user_id") or data.get("sender_id")

                # Reconstruct request with body
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception:
                pass

        # Set logging context
        set_context(request_id, user_id)

        # Log request
        logger.info(f"➡️ {request.method} {request.url.path}")

        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            # Log response
            logger.info(f"⬅️ {request.method} {request.url.path} - {response.status_code}")

            return response

        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            raise

        finally:
            clear_context()


# Convenience functions for logging with context
def log_info(message: str, **kwargs):
    """Log info with current context"""
    logger.bind(**kwargs).info(message)


def log_error(message: str, **kwargs):
    """Log error with current context"""
    logger.bind(**kwargs).error(message)


def log_warning(message: str, **kwargs):
    """Log warning with current context"""
    logger.bind(**kwargs).warning(message)


def log_debug(message: str, **kwargs):
    """Log debug with current context"""
    logger.bind(**kwargs).debug(message)
