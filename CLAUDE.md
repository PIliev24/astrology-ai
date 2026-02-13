# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered astrology API built with FastAPI, Supabase, and OpenAI Agents. Provides birth chart calculations, AI chat via WebSocket, compatibility analysis, and Stripe-based subscriptions. Production domain: aistrology.eu.

## Commands

```bash
# Install dependencies (uv is the package manager)
uv sync

# Run development server
python main.py
# or: uvicorn main:app --reload

# Docker
docker build -t astrology-api .
docker run -p 8000:8000 --env-file .env astrology-api
```

No test suite or linter is configured yet.

## Architecture

**Layered structure:** API routers → Service layer → Database (Supabase)

- `main.py` — FastAPI app entry point, registers routers, CORS, exception handlers
- `api/` — Route handlers. Each feature has a `*_router.py` and a subfolder with its service logic
- `services/` — Business logic (birth charts, compatibility, subscriptions, usage tracking)
- `core/` — Infrastructure: custom exception hierarchy (`core/exceptions.py`), HTTP clients (`core/clients/`), generic CRUD base (`core/database/base_service.py`)
- `ai_agents/` — OpenAI Agent definition (`astrology_specialist_agent.py`). Single agent with tools for chart retrieval, listing, and compatibility. Uses `gpt-5-mini` with streaming over WebSocket
- `models/` — Pydantic models for API requests/responses and database entities
- `config/settings.py` — Pydantic Settings with `@lru_cache`. Validates all env vars at startup
- `middleware/auth.py` — JWT authentication via Supabase
- `constants/` — Subscription plan limits and message templates
- `migrations/` — SQL migration files (run manually via Supabase dashboard/CLI)

**Key patterns:**
- `BaseService[ModelT, CreateT, UpdateT]` — Generic CRUD with user isolation (all queries filter by `user_id`)
- `AppException` hierarchy — Domain exceptions (`ChartNotFoundError`, `MessageLimitExceededError`, etc.) caught by global handlers in `core/error_handlers.py`
- Dependency injection via FastAPI's `Depends()` for auth and clients
- WebSocket endpoint (`/ws/chat`) for streaming AI responses
- Rolling 24-hour usage window for message limits (FREE: 1/day, BASIC: 3/day, PRO: unlimited)

## Environment

Requires `.env` file (see `.env.example`). Key variables: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `RAPIDAPI_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_BASIC`, `STRIPE_PRICE_ID_PRO`. The `SUPABASE_SECRET_KEY` is the service role key that bypasses RLS.

## Tech Stack

Python 3.12, FastAPI, Supabase (auth + Postgres), OpenAI Agents SDK (`openai-agents`), Stripe, httpx, geopy, timezonefinder, Pydantic v2, UV package manager.
