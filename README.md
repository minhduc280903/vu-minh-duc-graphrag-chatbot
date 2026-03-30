# 🤖 Smart Chatbot - Hybrid AI System

Hệ thống chatbot AI thông minh sử dụng kiến trúc **Hybrid (n8n + Python)** cho Facebook Messenger và Zalo.

## ✨ Tính năng

| # | Tính năng | Mô tả |
|---|-----------|-------|
| 1 | **Đa phương thức** | Hiểu text, ảnh, audio |
| 2 | **Cá nhân hóa** | Gọi tên khách hàng |
| 3 | **Gửi ảnh tự động** | Sản phẩm, báo giá, chứng nhận |
| 4 | **Nhường Admin** | Tự động dừng 30 phút khi admin chat |
| 5 | **Thông báo Zalo** | Gửi lead về cho Telesale |
| 6 | **Bám đuổi 24h+** | Follow-up tự động |
| 7 | **Mời Zalo** | Tự động mời vào nhóm |
| 8 | **Debouncing** | Đợi khách nhắn xong mới trả lời |
| 9 | **Human-like** | Chia nhỏ và gõ như người thật |
| 10 | **GraphRAG** | Database thông minh |

## 🏗️ Tech Stack

- **Orchestration:** n8n (self-hosted)
- **AI:** Gemini 1.5 Pro + LangChain
- **Graph Database:** Neo4j (GraphRAG)
- **Cache:** Redis
- **API:** Python FastAPI
- **Container:** Docker Compose

## 🚀 Quick Start

### 1. Clone & Setup

```bash
cd smart-chatbot
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Services

```bash
docker-compose up -d
```

### 3. Access

- **n8n:** http://localhost:5678
- **API Docs:** http://localhost:8000/docs
- **Neo4j Browser:** http://localhost:7474

### 4. Setup Neo4j Schema

```bash
# In Neo4j Browser, run:
# Open knowledge/schema.cypher and execute
```

### 5. Import n8n Workflows

1. Open n8n (http://localhost:5678)
2. Import `n8n/workflows/messenger_webhook.json`
3. Import `n8n/workflows/response_sender.json`

## 📁 Project Structure

```
smart-chatbot/
├── docker-compose.yml      # Full stack setup
├── .env.example            # Environment template
├── python/                 # FastAPI application
│   ├── app/
│   │   ├── main.py         # Entry point
│   │   ├── config.py       # Settings
│   │   ├── routers/        # API endpoints
│   │   │   ├── webhook.py  # FB/Zalo webhooks
│   │   │   ├── chat.py     # Chat processing
│   │   │   └── health.py   # Health checks
│   │   └── services/       # Business logic
│   │       ├── ai_brain.py      # Gemini + GraphRAG
│   │       ├── debouncer.py     # Message aggregation
│   │       ├── redis_client.py  # State management
│   │       ├── neo4j_client.py  # Graph queries
│   │       ├── messenger_api.py # FB Send API
│   │       ├── zalo_api.py      # Zalo OA/ZNS
│   │       ├── response_splitter.py
│   │       └── lead_extractor.py
│   ├── Dockerfile
│   └── requirements.txt
├── n8n/
│   └── workflows/          # n8n workflow templates
│       ├── messenger_webhook.json
│       └── response_sender.json
└── knowledge/
    └── schema.cypher       # Neo4j GraphRAG schema
```

## ⚙️ Configuration

Edit `.env` file:

```env
# AI
GOOGLE_API_KEY=your_gemini_key

# Facebook
FB_VERIFY_TOKEN=your_verify_token
FB_PAGE_ACCESS_TOKEN=your_page_token
FB_ADMIN_PSID=admin_page_scoped_id

# Zalo
ZALO_ACCESS_TOKEN=your_zalo_token
ZALO_GROUP_LINK=https://zalo.me/g/xxx

# Behavior
DEBOUNCE_SECONDS=7
ADMIN_HANDOVER_MINUTES=30
```

## 📖 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/messenger` | GET/POST | FB Webhook |
| `/webhook/zalo` | POST | Zalo Webhook |
| `/chat/process` | POST | Process messages |
| `/health` | GET | Health check |

## 🔧 Development

```bash
# Install dependencies
cd python
pip install uv
uv pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v
```

## 📝 License

MIT License
