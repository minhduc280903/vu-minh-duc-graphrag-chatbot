"""
Health Check Router
Endpoints for health monitoring
"""
from fastapi import APIRouter

from app.services.redis_client import redis_manager
from app.services.neo4j_client import neo4j_manager

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with service status"""
    services = {
        "api": "healthy",
        "redis": "unknown",
        "neo4j": "unknown"
    }
    
    # Check Redis
    try:
        if redis_manager.client:
            await redis_manager.client.ping()
            services["redis"] = "healthy"
        else:
            services["redis"] = "not_connected"
    except Exception as e:
        services["redis"] = f"error: {str(e)}"
    
    # Check Neo4j
    try:
        if neo4j_manager.driver:
            await neo4j_manager.run_query("RETURN 1")
            services["neo4j"] = "healthy"
        else:
            services["neo4j"] = "not_connected"
    except Exception as e:
        services["neo4j"] = f"error: {str(e)}"
    
    # Overall status
    all_healthy = all(s == "healthy" for s in services.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": services
    }
