"""
Embedding Service
Handles vector embedding generation using Google text-embedding-004
"""
from typing import List, Optional

from loguru import logger

from app.config import get_settings

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("GoogleGenerativeAIEmbeddings not available")


class EmbeddingService:
    """
    Embedding service using Google's text-embedding-004 model
    Dimension: 768 (configured in settings)
    
    Note: Do NOT use gemini-1.5-pro for embeddings - it's a generative model
    Always use dedicated embedding models like text-embedding-004
    """
    
    def __init__(self):
        self.model: Optional[GoogleGenerativeAIEmbeddings] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize embedding model"""
        if self._initialized:
            return
        
        if not EMBEDDINGS_AVAILABLE:
            logger.warning("⚠️ Embeddings not available - install langchain-google-genai")
            return
        
        settings = get_settings()
        
        if not settings.google_api_key:
            logger.warning("⚠️ No Google API key configured for embeddings")
            return
        
        try:
            # Use dedicated embedding model (NOT gemini-1.5-pro!)
            self.model = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.google_api_key
            )
            self._initialized = True
            logger.info(f"✅ Embedding service initialized (dim={settings.vector_dimension})")
            
        except Exception as e:
            logger.error(f"❌ Embedding initialization failed: {e}")
    
    async def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for single text
        Returns 768-dimensional vector
        """
        await self.initialize()
        
        if not self._initialized or not self.model:
            return None
        
        try:
            # Use aembed_query for async single text
            vector = await self.model.aembed_query(text)
            logger.debug(f"Generated embedding: {len(vector)} dimensions")
            return vector
            
        except Exception as e:
            logger.error(f"❌ Embedding failed: {e}")
            return None
    
    async def embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings for multiple texts (batch)
        More efficient than calling embed_text multiple times
        """
        await self.initialize()
        
        if not self._initialized or not self.model:
            return None
        
        try:
            # Use aembed_documents for async batch
            vectors = await self.model.aembed_documents(texts)
            logger.debug(f"Generated {len(vectors)} embeddings")
            return vectors
            
        except Exception as e:
            logger.error(f"❌ Batch embedding failed: {e}")
            return None
    
    async def embed_product(
        self, 
        name: str, 
        description: str = "",
        category: str = ""
    ) -> Optional[List[float]]:
        """
        Generate embedding for a product
        Combines name, description, and category for richer context
        """
        # Combine fields for better semantic representation
        text = f"{name}"
        if description:
            text += f": {description}"
        if category:
            text += f" (Danh mục: {category})"
        
        return await self.embed_text(text)


# Global instance
embedding_service = EmbeddingService()
