// Neo4j GraphRAG Schema for Smart Chatbot
// Run this script via Neo4j Browser or cypher-shell

// ============ Clear existing schema (optional) ============
// MATCH (n) DETACH DELETE n;

// ============ Constraints ============
CREATE CONSTRAINT product_id IF NOT EXISTS 
FOR (p:Product) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT certificate_id IF NOT EXISTS 
FOR (c:Certificate) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT feedback_id IF NOT EXISTS 
FOR (f:Feedback) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT customer_id IF NOT EXISTS 
FOR (c:Customer) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT category_name IF NOT EXISTS 
FOR (c:Category) REQUIRE c.name IS UNIQUE;

// ============ Indexes for search ============

// Full-text search index for products
CREATE FULLTEXT INDEX product_search IF NOT EXISTS 
FOR (p:Product) ON EACH [p.name, p.description, p.keywords];

// Full-text search for feedbacks
CREATE FULLTEXT INDEX feedback_search IF NOT EXISTS 
FOR (f:Feedback) ON EACH [f.content];

// ============ Vector Index for Semantic Search ============
// Requires Neo4j 5.x with vector support

CREATE VECTOR INDEX product_embedding IF NOT EXISTS
FOR (p:Product) ON p.embedding
OPTIONS {
    indexConfig: {
        `vector.dimensions`: 768,
        `vector.similarity_function`: 'cosine'
    }
};

// ============ Sample Data Structure ============

// Create Categories
CREATE (c1:Category {name: 'Điện tử', description: 'Thiết bị điện tử'})
CREATE (c2:Category {name: 'Gia dụng', description: 'Đồ gia dụng'})
CREATE (c3:Category {name: 'Thời trang', description: 'Quần áo, phụ kiện'});

// Create Sample Product
CREATE (p:Product {
    id: 'PROD001',
    name: 'Máy lọc không khí XYZ',
    price: 2500000,
    description: 'Máy lọc không khí thông minh, diệt 99.9% vi khuẩn',
    keywords: 'máy lọc, không khí, vi khuẩn, thông minh',
    image_url: 'https://example.com/images/product001.jpg',
    stock: 50,
    created_at: datetime()
});

// Create Certificate
CREATE (cert:Certificate {
    id: 'CERT001',
    name: 'Chứng nhận ISO 9001',
    issuer: 'Bộ Khoa học Công nghệ',
    year: 2024,
    image_url: 'https://example.com/certs/iso9001.jpg'
});

// Create Feedback
CREATE (fb:Feedback {
    id: 'FB001',
    content: 'Sản phẩm rất tốt, con tôi hết ho ngay sau 1 tuần sử dụng',
    rating: 5,
    customer_name: 'Chị Hương',
    image_url: 'https://example.com/feedback/fb001.jpg',
    created_at: datetime()
});

// Create Customer
CREATE (cust:Customer {
    id: 'CUST001',
    fb_psid: '1234567890',
    name: 'Nguyễn Văn A',
    phone: '0912345678',
    source_page: 'Fanpage ABC',
    created_at: datetime()
});

// ============ Create Relationships ============

// Product belongs to Category
MATCH (p:Product {id: 'PROD001'}), (c:Category {name: 'Gia dụng'})
CREATE (p)-[:BELONGS_TO]->(c);

// Product has Certificate
MATCH (p:Product {id: 'PROD001'}), (cert:Certificate {id: 'CERT001'})
CREATE (p)-[:HAS_CERTIFICATE]->(cert);

// Product has Feedback
MATCH (p:Product {id: 'PROD001'}), (fb:Feedback {id: 'FB001'})
CREATE (p)-[:HAS_FEEDBACK]->(fb);

// Customer interested in Product
MATCH (cust:Customer {id: 'CUST001'}), (p:Product {id: 'PROD001'})
CREATE (cust)-[:INTERESTED_IN {timestamp: datetime()}]->(p);

// ============ Useful Queries ============

// Find product with all related info (GraphRAG query)
// MATCH (p:Product {id: 'PROD001'})
// OPTIONAL MATCH (p)-[:HAS_CERTIFICATE]->(cert)
// OPTIONAL MATCH (p)-[:HAS_FEEDBACK]->(fb)
// OPTIONAL MATCH (p)-[:BELONGS_TO]->(cat)
// RETURN p, collect(DISTINCT cert) as certificates, collect(DISTINCT fb) as feedbacks, cat;

// Full-text search
// CALL db.index.fulltext.queryNodes('product_search', 'máy lọc không khí')
// YIELD node, score
// RETURN node.name, node.price, score
// ORDER BY score DESC;

// Vector similarity search
// MATCH (p:Product)
// WHERE p.embedding IS NOT NULL
// CALL db.index.vector.queryNodes('product_embedding', 5, $queryVector)
// YIELD node, score
// RETURN node.name, score;
