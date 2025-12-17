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
```

### 4. Run the API server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 5. Access API documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/ingest` | Analyze text and extract memories |
| POST | `/v1/memories` | Force/manual memory creation |
| GET | `/v1/memories` | Search and list memories |
| GET | `/v1/memories/{id}` | Get single memory |
| PATCH | `/v1/memories/{id}` | Update memory |
| DELETE | `/v1/memories/{id}` | Delete memory |
| POST | `/v1/context` | RAG context synthesis |
| GET | `/v1/dump` | Export memories |

## Memory Types

- **FACT**: Stable, objective information (name, skills, preferences)
- **STATE**: Temporary conditions (mood, health, workload)
- **EPISODE**: Past events or experiences
- **POLICY**: User rules or preferences

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
