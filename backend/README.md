# AgriConnect AI - Backend

This is the core Python backend for the AgriConnect AI platform. It powers the Voice-to-Text listings, AI Negotiation Engine, and all database interactions.

## Stack
- **Framework:** FastAPI
- **Database:** PostgreSQL via `asyncpg` and SQLAlchemy
- **Migrations:** Alembic
- **Caching:** Redis
- **AI Gateway:** Groq API + Faster-Whisper + Vision API

## Getting Started

1. Ensure Docker is running the core databases (`docker compose up -d` from the root).
2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```
3. Apply database migrations:
   ```bash
   alembic upgrade head
   ```
4. Start the server:
   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```

## Key Services
- **`negotiation_engine.py`**: Runs the pricing math and strict admin bounds.
- **`llm_gateway.py`**: Translates math decisions into human language (Telugu/English).
- **`stt_service.py`**: Handles voice transcription.