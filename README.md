# Antigravity Cortex (Knowledge Core)

AI-powered knowledge management microservice for storing and retrieving user memories with vector search and context synthesis.

## Quick Start

### 1. Start PostgreSQL with pgvector

```bash
docker-compose up -d
```

This starts PostgreSQL 16 with pgvector extension and runs the initial schema migration.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` file:
```
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+asyncpg://cortex:cortex_password@localhost:5432/cortex_db
API_KEY=cortex_secret_key_2025
```

> [!IMPORTANT]
> The `API_KEY` is required for all requests via the `X-API-KEY` header.

### 4. Run the API server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 5. Access UI and documentation

- **Memory Gardener UI**: http://localhost:8000/ui (Default API Key: `cortex_secret_key_2025`)
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/ingest` | **Async** text analysis (returns 202 + Job ID) |
| GET | `/v1/ingest/{id}` | Check status of ingestion job |
| POST | `/v1/memories` | Force/manual memory creation |
| GET | `/v1/memories` | Search with **Ranking Policies** |
| GET | `/v1/memories/{id}` | Get single memory (RLS enforced) |
| PATCH | `/v1/memories/{id}` | Update memory |
| DELETE | `/v1/memories/{id}` | Delete memory |
| POST | `/v1/context` | RAG context synthesis |
| GET | `/v1/dump` | Export memories |
| GET | `/health` | Enhanced connectivity check |

## Ranking Policies

The retrieval logic uses a multi-factor ranking system:
1. **Semantic Similarity**: Vector cosine similarity.
2. **Importance (1-5)**: Weighted multiplier.
3. **Confidence (0-1)**: AI certainty weight.
4. **Recency Decay**: Applied to `STATE` and `EPISODE` memories to prioritize fresher information.
5. **Temporal Cutoff**: Automatic removal of expired or superseded `STATE` memories.

## Security & Isolation

- **X-API-KEY**: Header-based authentication for all routes.
- **Row Level Security (RLS)**: PostgreSQL-level isolation ensuring users only access their own memories.
- **Audit Logs**: Full history of changes for every memory.

## Architecture

```
┌─────────────────────────────────────────────┐
│           Antigravity Cortex                │
├─────────────────────────────────────────────┤
│  FastAPI → Memory Manager → PostgreSQL      │
│     ↓           ↓              ↓            │
│  Routers    AI Analyzer    pgvector         │
│              (Gemini)      (HNSW)           │
└─────────────────────────────────────────────┘
```

## License

Private - Antigravity OS
