"""
Smart Chatbot Configuration
Using Pydantic Settings for type-safe environment variables
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # ============ Redis ============
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    
    # ============ Neo4j ============
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    
    # ============ AI/LLM ============
    google_api_key: str = ""
    openai_api_key: str = ""
    
    # ============ Facebook ============
    fb_verify_token: str = ""
    fb_page_access_token: str = ""
    fb_app_secret: str = ""
    fb_admin_psids: str = ""  # Comma-separated list of admin PSIDs
    
    # ============ Zalo ============
    zalo_oa_id: str = ""
    zalo_oa_secret: str = ""
    zalo_access_token: str = ""
    zalo_zns_template_id: str = ""
    zalo_group_link: str = ""
    
    # ============ Telesale ============
    telesale_phones: str = ""  # Comma-separated phone numbers
    
    # ============ Telegram (Free alternative to Zalo ZNS) ============
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""  # Group or channel ID for lead notifications
    
    # ============ Chatbot Behavior ============
    debounce_seconds: int = 7
    debounce_quick_seconds: int = 3  # For messages ending with ?
    admin_handover_minutes: int = 30
    followup_hours: int = 24
    max_followups: int = 3
    
    # ============ n8n / Webhook ============
    webhook_url: str = "http://localhost:5678"
    
    # ============ AI Model ============
    # Gemini model names - use stable versions
    gemini_model: str = "gemini-2.0-flash-exp"  # Or "gemini-1.5-flash-latest"
    # Vector dimension must match embedding model:
    # - text-embedding-004 (Google) = 768
    # - text-embedding-3-small (OpenAI) = 1536
    vector_dimension: int = 768
    
    # ============ Feature Toggles (Demo Mode) ============
    enable_zalo_zns: bool = False  # Disable to save cost in demo
    enable_telegram_notify: bool = True  # Free alternative
    
    def get_admin_list(self) -> list:
        """Parse comma-separated admin PSIDs into list"""
        if not self.fb_admin_psids:
            return []
        return [psid.strip() for psid in self.fb_admin_psids.split(",") if psid.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env like N8N_*, POSTGRES_*


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
