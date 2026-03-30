"""
Neo4j Client for GraphRAG Knowledge Base
Handles entity storage, relationship queries, and vector search
"""
from typing import Optional, Any

from neo4j import AsyncGraphDatabase
from loguru import logger


class Neo4jManager:
    """Async Neo4j connection manager for GraphRAG"""
    
    def __init__(self):
        self.driver = None
    
    async def connect(self, uri: str, user: str, password: str):
        """Initialize Neo4j connection"""
        self.driver = AsyncGraphDatabase.driver(
            uri, 
            auth=(user, password)
        )
        # Verify connectivity
        async with self.driver.session() as session:
            await session.run("RETURN 1")
        logger.info(f"Neo4j connected to {uri}")
    
    async def disconnect(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")
    
    async def run_query(
        self, 
        query: str, 
        params: dict = None
    ) -> list[dict]:
        """Execute a Cypher query and return results"""
        async with self.driver.session() as session:
            result = await session.run(query, params or {})
            records = await result.data()
            return records
    
    # ============ Schema Setup ============
    
    async def setup_schema(self):
        """Initialize GraphRAG schema with constraints and indexes"""
        queries = [
            # Constraints
            "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT certificate_id IF NOT EXISTS FOR (c:Certificate) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
            
            # Indexes for full-text search
            """
            CREATE FULLTEXT INDEX product_search IF NOT EXISTS 
            FOR (p:Product) ON EACH [p.name, p.description]
            """,
            
            # Vector index for semantic search (Neo4j 5.x)
            """
            CREATE VECTOR INDEX product_embedding IF NOT EXISTS
            FOR (p:Product) ON p.embedding
            OPTIONS {indexConfig: {
                `vector.dimensions`: 768,
                `vector.similarity_function`: 'cosine'
            }}
            """
        ]
        
        for query in queries:
            try:
                await self.run_query(query)
            except Exception as e:
                logger.warning(f"Schema setup warning: {e}")
        
        logger.info("GraphRAG schema initialized")
    
    # ============ Product Methods ============
    
    async def create_product(
        self,
        id: str,
        name: str,
        price: float,
        description: str,
        image_url: str = None,
        embedding: list[float] = None,
        category: str = None,
        auto_embed: bool = True
    ) -> dict:
        """
        Create or update a product node
        
        Args:
            auto_embed: If True and embedding is None, automatically generate embedding
        """
        # Auto-generate embedding if not provided
        if auto_embed and embedding is None:
            try:
                from app.services.embedding_service import embedding_service
                embedding = await embedding_service.embed_product(
                    name=name,
                    description=description,
                    category=category or ""
                )
                if embedding:
                    from loguru import logger
                    logger.info(f"✅ Auto-generated embedding for product: {name}")
            except Exception as e:
                from loguru import logger
                logger.warning(f"⚠️ Auto-embed failed for {name}: {e}")
        
        query = """
        MERGE (p:Product {id: $id})
        SET p.name = $name,
            p.price = $price,
            p.description = $description,
            p.image_url = $image_url,
            p.embedding = $embedding,
            p.category = $category,
            p.updated_at = datetime()
        RETURN p
        """
        result = await self.run_query(query, {
            "id": id,
            "name": name,
            "price": price,
            "description": description,
            "image_url": image_url,
            "embedding": embedding,
            "category": category
        })
        return result[0] if result else None
    
    async def find_products_by_text(
        self, 
        search_text: str, 
        limit: int = 5
    ) -> list[dict]:
        """Full-text search for products"""
        query = """
        CALL db.index.fulltext.queryNodes('product_search', $search_text)
        YIELD node, score
        RETURN node.id AS id, 
               node.name AS name, 
               node.price AS price,
               node.description AS description,
               node.image_url AS image_url,
               score
        ORDER BY score DESC
        LIMIT $limit
        """
        return await self.run_query(query, {
            "search_text": search_text,
            "limit": limit
        })
    
    async def find_products_by_vector(
        self, 
        embedding: list[float], 
        limit: int = 5
    ) -> list[dict]:
        """Semantic vector search for products"""
        query = """
        CALL db.index.vector.queryNodes('product_embedding', $limit, $embedding)
        YIELD node, score
        RETURN node.id AS id,
               node.name AS name,
               node.price AS price,
               node.description AS description,
               node.image_url AS image_url,
               score
        """
        return await self.run_query(query, {
            "embedding": embedding,
            "limit": limit
        })
    
    # ============ Certificate Methods ============
    
    async def add_certificate_to_product(
        self,
        product_id: str,
        cert_id: str,
        cert_name: str,
        issuer: str,
        image_url: str = None
    ):
        """Link a certificate to a product"""
        query = """
        MATCH (p:Product {id: $product_id})
        MERGE (c:Certificate {id: $cert_id})
        SET c.name = $cert_name,
            c.issuer = $issuer,
            c.image_url = $image_url
        MERGE (p)-[:HAS_CERTIFICATE]->(c)
        RETURN p, c
        """
        return await self.run_query(query, {
            "product_id": product_id,
            "cert_id": cert_id,
            "cert_name": cert_name,
            "issuer": issuer,
            "image_url": image_url
        })
    
    async def get_product_certificates(self, product_id: str) -> list[dict]:
        """Get all certificates for a product"""
        query = """
        MATCH (p:Product {id: $product_id})-[:HAS_CERTIFICATE]->(c:Certificate)
        RETURN c.id AS id, c.name AS name, c.issuer AS issuer, c.image_url AS image_url
        """
        return await self.run_query(query, {"product_id": product_id})
    
    # ============ Feedback Methods ============
    
    async def add_feedback_to_product(
        self,
        product_id: str,
        feedback_id: str,
        content: str,
        rating: int,
        customer_name: str = None,
        image_url: str = None
    ):
        """Add customer feedback to a product"""
        query = """
        MATCH (p:Product {id: $product_id})
        CREATE (f:Feedback {
            id: $feedback_id,
            content: $content,
            rating: $rating,
            customer_name: $customer_name,
            image_url: $image_url,
            created_at: datetime()
        })
        CREATE (p)-[:HAS_FEEDBACK]->(f)
        RETURN p, f
        """
        return await self.run_query(query, {
            "product_id": product_id,
            "feedback_id": feedback_id,
            "content": content,
            "rating": rating,
            "customer_name": customer_name,
            "image_url": image_url
        })
    
    async def get_product_feedbacks(
        self, 
        product_id: str, 
        limit: int = 5
    ) -> list[dict]:
        """Get recent feedbacks for a product"""
        query = """
        MATCH (p:Product {id: $product_id})-[:HAS_FEEDBACK]->(f:Feedback)
        RETURN f.id AS id, 
               f.content AS content, 
               f.rating AS rating,
               f.customer_name AS customer_name,
               f.image_url AS image_url
        ORDER BY f.created_at DESC
        LIMIT $limit
        """
        return await self.run_query(query, {
            "product_id": product_id,
            "limit": limit
        })
    
    # ============ GraphRAG Query Methods ============
    
    async def get_product_full_context(self, product_id: str) -> dict:
        """
        Get complete product context for GraphRAG
        Including related certificates, feedbacks, and similar products
        """
        query = """
        MATCH (p:Product {id: $product_id})
        OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(cert:Certificate)
        OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(fb:Feedback)
        WITH p, 
             collect(DISTINCT cert) AS certificates,
             collect(DISTINCT fb) AS feedbacks
        RETURN p AS product,
               certificates,
               feedbacks,
               size(certificates) AS cert_count,
               size(feedbacks) AS feedback_count
        """
        result = await self.run_query(query, {"product_id": product_id})
        return result[0] if result else None
    
    async def answer_question_with_graph(
        self, 
        question: str,
        entities: list[str]
    ) -> dict:
        """
        Enhanced GraphRAG: Query graph based on extracted entities
        Returns structured context for LLM
        """
        # Find products matching entities
        query = """
        UNWIND $entities AS entity
        MATCH (p:Product)
        WHERE toLower(p.name) CONTAINS toLower(entity)
           OR toLower(p.description) CONTAINS toLower(entity)
        WITH p, count(*) AS relevance
        ORDER BY relevance DESC
        LIMIT 3
        
        OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(c:Certificate)
        OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(f:Feedback)
        
        RETURN p.id AS product_id,
               p.name AS product_name,
               p.price AS price,
               p.description AS description,
               p.image_url AS product_image,
               collect(DISTINCT {
                   name: c.name, 
                   issuer: c.issuer,
                   image: c.image_url
               }) AS certificates,
               collect(DISTINCT {
                   content: f.content,
                   rating: f.rating,
                   image: f.image_url
               })[0..3] AS top_feedbacks
        """
        return await self.run_query(query, {"entities": entities})


# Global instance
neo4j_manager = Neo4jManager()
