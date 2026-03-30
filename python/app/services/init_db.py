"""
Database Initialization Service
Auto-seeds Neo4j schema and sample data on startup
"""
from loguru import logger

from app.services.neo4j_client import neo4j_manager


async def init_neo4j_schema():
    """
    Initialize Neo4j GraphRAG schema with constraints, indexes, and sample data.
    Called during application startup.
    """
    logger.info("🔧 Initializing Neo4j GraphRAG schema...")

    # ============ Constraints ============
    constraints = [
        "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT certificate_id IF NOT EXISTS FOR (c:Certificate) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT feedback_id IF NOT EXISTS FOR (f:Feedback) REQUIRE f.id IS UNIQUE",
        "CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
    ]

    for query in constraints:
        try:
            await neo4j_manager.run_query(query)
        except Exception as e:
            logger.debug(f"Constraint may already exist: {e}")

    logger.info("✅ Constraints created")

    # ============ Fulltext Indexes ============
    fulltext_indexes = [
        """
        CREATE FULLTEXT INDEX product_search IF NOT EXISTS
        FOR (p:Product) ON EACH [p.name, p.description, p.keywords]
        """,
        """
        CREATE FULLTEXT INDEX feedback_search IF NOT EXISTS
        FOR (f:Feedback) ON EACH [f.content]
        """,
    ]

    for query in fulltext_indexes:
        try:
            await neo4j_manager.run_query(query)
        except Exception as e:
            logger.debug(f"Index may already exist: {e}")

    logger.info("✅ Fulltext indexes created")

    # ============ Vector Index (Neo4j 5.x) ============
    vector_index = """
    CREATE VECTOR INDEX product_embedding IF NOT EXISTS
    FOR (p:Product) ON p.embedding
    OPTIONS {
        indexConfig: {
            `vector.dimensions`: 768,
            `vector.similarity_function`: 'cosine'
        }
    }
    """

    try:
        await neo4j_manager.run_query(vector_index)
        logger.info("✅ Vector index created")
    except Exception as e:
        logger.warning(f"Vector index creation failed (may need Neo4j 5.x): {e}")

    # ============ Check if sample data exists ============
    check_data = await neo4j_manager.run_query("MATCH (p:Product) RETURN count(p) AS count")
    if check_data and check_data[0].get("count", 0) > 0:
        logger.info(f"📦 Found {check_data[0]['count']} existing products, skipping seed data")
        return

    # ============ Seed Sample Data ============
    logger.info("🌱 Seeding sample data...")

    # Create Categories
    await neo4j_manager.run_query("""
        MERGE (c1:Category {name: 'Gia dụng'})
        SET c1.description = 'Đồ gia dụng thông minh'
        MERGE (c2:Category {name: 'Điện tử'})
        SET c2.description = 'Thiết bị điện tử'
        MERGE (c3:Category {name: 'Thời trang'})
        SET c3.description = 'Quần áo, phụ kiện'
    """)

    # Create Sample Products
    sample_products = [
        {
            "id": "PROD001",
            "name": "Máy lọc không khí XYZ Pro",
            "price": 2500000,
            "description": "Máy lọc không khí thông minh, diệt 99.9% vi khuẩn, lọc bụi mịn PM2.5. Phù hợp phòng 30-50m2.",
            "keywords": "máy lọc, không khí, vi khuẩn, thông minh, PM2.5",
            "image_url": "https://example.com/images/air-purifier.jpg",
            "category": "Gia dụng"
        },
        {
            "id": "PROD002",
            "name": "Nồi chiên không dầu 5L",
            "price": 1800000,
            "description": "Nồi chiên không dầu đa năng 5 lít, 8 chế độ nấu, màn hình cảm ứng. Tiết kiệm 80% dầu mỡ.",
            "keywords": "nồi chiên, không dầu, air fryer, healthy",
            "image_url": "https://example.com/images/air-fryer.jpg",
            "category": "Gia dụng"
        },
        {
            "id": "PROD003",
            "name": "Robot hút bụi thông minh",
            "price": 4500000,
            "description": "Robot hút bụi lau nhà tự động, điều khiển qua app, bản đồ thông minh, pin 3000mAh.",
            "keywords": "robot, hút bụi, lau nhà, thông minh, tự động",
            "image_url": "https://example.com/images/robot-vacuum.jpg",
            "category": "Gia dụng"
        },
    ]

    for product in sample_products:
        await neo4j_manager.run_query("""
            MERGE (p:Product {id: $id})
            SET p.name = $name,
                p.price = $price,
                p.description = $description,
                p.keywords = $keywords,
                p.image_url = $image_url,
                p.stock = 50,
                p.created_at = datetime()
            WITH p
            MATCH (c:Category {name: $category})
            MERGE (p)-[:BELONGS_TO]->(c)
        """, product)

    logger.info(f"✅ Created {len(sample_products)} sample products")

    # Create Certificates
    certificates = [
        {
            "product_id": "PROD001",
            "cert_id": "CERT001",
            "name": "Chứng nhận ISO 9001:2015",
            "issuer": "Tổ chức Tiêu chuẩn Quốc tế",
            "image_url": "https://example.com/certs/iso9001.jpg"
        },
        {
            "product_id": "PROD001",
            "cert_id": "CERT002",
            "name": "Chứng nhận An toàn Điện",
            "issuer": "Bộ Công Thương",
            "image_url": "https://example.com/certs/safety.jpg"
        },
    ]

    for cert in certificates:
        await neo4j_manager.run_query("""
            MATCH (p:Product {id: $product_id})
            MERGE (c:Certificate {id: $cert_id})
            SET c.name = $name,
                c.issuer = $issuer,
                c.image_url = $image_url
            MERGE (p)-[:HAS_CERTIFICATE]->(c)
        """, cert)

    logger.info(f"✅ Created {len(certificates)} certificates")

    # Create Feedbacks
    feedbacks = [
        {
            "product_id": "PROD001",
            "feedback_id": "FB001",
            "content": "Sản phẩm rất tốt, con tôi hết ho sau 1 tuần sử dụng. Không khí trong phòng thơm tho hẳn!",
            "rating": 5,
            "customer_name": "Chị Hương - HN"
        },
        {
            "product_id": "PROD001",
            "feedback_id": "FB002",
            "content": "Máy chạy êm, thiết kế đẹp. Giao hàng nhanh, đóng gói cẩn thận. 5 sao!",
            "rating": 5,
            "customer_name": "Anh Minh - SG"
        },
        {
            "product_id": "PROD002",
            "feedback_id": "FB003",
            "content": "Nồi chiên ngon lắm, làm khoai tây chiên giòn tan mà không cần dầu. Cả nhà ai cũng thích!",
            "rating": 5,
            "customer_name": "Chị Mai - DN"
        },
    ]

    for fb in feedbacks:
        await neo4j_manager.run_query("""
            MATCH (p:Product {id: $product_id})
            CREATE (f:Feedback {
                id: $feedback_id,
                content: $content,
                rating: $rating,
                customer_name: $customer_name,
                created_at: datetime()
            })
            CREATE (p)-[:HAS_FEEDBACK]->(f)
        """, fb)

    logger.info(f"✅ Created {len(feedbacks)} feedbacks")
    logger.info("🎉 Neo4j GraphRAG schema initialization complete!")


async def generate_product_embeddings():
    """
    Generate embeddings for all products that don't have one.
    Should be called after init_neo4j_schema.
    """
    from app.services.embedding_service import embedding_service

    # Get products without embeddings
    products = await neo4j_manager.run_query("""
        MATCH (p:Product)
        WHERE p.embedding IS NULL
        RETURN p.id AS id, p.name AS name, p.description AS description, p.keywords AS keywords
    """)

    if not products:
        logger.info("📊 All products already have embeddings")
        return

    logger.info(f"🔄 Generating embeddings for {len(products)} products...")

    for product in products:
        try:
            # Combine text for embedding
            text = f"{product['name']}: {product.get('description', '')} {product.get('keywords', '')}"
            embedding = await embedding_service.embed_text(text)

            if embedding:
                await neo4j_manager.run_query("""
                    MATCH (p:Product {id: $id})
                    SET p.embedding = $embedding
                """, {"id": product["id"], "embedding": embedding})
                logger.debug(f"✅ Embedded: {product['name']}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to embed {product['name']}: {e}")

    logger.info("✅ Product embeddings generated")
