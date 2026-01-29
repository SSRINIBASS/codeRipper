# Repo Intelligence Platform

> Convert undocumented GitHub repositories into understandable, searchable, and teachable systems.

## Overview

An API-first platform that ingests GitHub repositories, performs semantic indexing, generates documentation, and provides an interactive tutor for understanding codebases.

## Features

- **Repository Ingestion** - Clone and analyze GitHub repositories
- **Semantic Search** - Natural language search over code
- **Auto Documentation** - LLM-generated README and architecture docs  
- **Interactive Tutor** - Q&A grounded strictly in the codebase
- **Anti-Hallucination** - All answers cite specific code references

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API key

### Setup

1. **Clone and configure:**
   ```bash
   cd codeRipper
   cp .env.example .env
   # Edit .env with your OPENAI_API_KEY
   ```

2. **Start services:**
   ```bash
   docker-compose up -d
   ```

3. **Run migrations:**
   ```bash
   docker-compose exec app alembic upgrade head
   ```

4. **Access API docs:**
   Open http://localhost:8000/docs

## API Endpoints

### Repositories
- `POST /repos/ingest` - Ingest a GitHub repository
- `GET /repos/{id}/status` - Get repository status
- `GET /repos/{id}/structure` - Get file structure
- `GET /repos/{id}/entrypoints` - Get detected entry points

### Intelligence  
- `POST /intelligence/{id}/index` - Start semantic indexing
- `GET /intelligence/{id}/search` - Semantic code search
- `POST /intelligence/{id}/docs` - Generate documentation
- `GET /intelligence/{id}/docs/readme` - Get generated README

### Tutor
- `POST /tutor/{id}/session` - Create tutor session
- `POST /tutor/{id}/ask` - Ask a question

### Jobs
- `GET /jobs/{id}` - Get job status

## Repository Lifecycle

```
CREATED → CLONED → STRUCTURED → INDEXED → DOCS_GENERATED → READY
                                    ↓
                                 FAILED
```

## Architecture

```
app/
├── api/           # FastAPI routers (thin controllers)
├── services/      # Business logic (fat services)
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic request/response models
├── core/          # Utilities (git, llm, vector_store)
├── middleware/    # Auth, rate limiting, logging
└── worker/        # Background job processor
```

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run locally
uvicorn app.main:app --reload

# Run worker
python -m app.worker.runner

# Run tests
pytest tests/ -v
```

## Configuration

Key environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `OPENAI_API_KEY` | OpenAI API key | Required |
| `STORAGE_PATH` | Data storage path | `./data` |
| `SIMILARITY_THRESHOLD` | Vector search threshold | `0.65` |

See `.env.example` for all options.

## License

MIT
