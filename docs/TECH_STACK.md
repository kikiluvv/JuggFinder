# Tech Stack

## Language
- **Python 3.12+** — Backend, scraping, scoring pipeline
- **TypeScript** — Frontend

## Scraping
- **`playwright`** — Browser automation for Google Maps (JS-rendered pages require a full browser)
- **`httpx`** — Async HTTP client for fetching and evaluating business websites (lightweight; no browser needed for static HTML analysis)

## AI / Intelligence
- **`google-generativeai`** — Gemini 1.5 Flash, free tier (15 RPM, 1M tokens/day). Primary LLM for website quality scoring.
- **`groq`** — Groq SDK, free tier (Llama 3 8B). Automatic fallback when Gemini rate-limits.

## Scheduling
- **`apscheduler`** — `AsyncIOScheduler` running inside the FastAPI process. Fires the daily scrape job at a configurable time without any OS-level cron setup.

## Reliability
- **`tenacity`** — Retry logic for API calls and HTTP requests (handles timeouts, rate limits, transient network errors gracefully)

## Database
- **`sqlalchemy`** + **`aiosqlite`** — Async SQLite ORM. Single local file: `leads.db`. No database server required.

## Backend API
- **`fastapi`** + **`uvicorn`** — ASGI web server and REST API framework
- **`python-dotenv`** — `.env` file loading for API keys and config values

## Frontend
- **Vite** + **React** + **TypeScript** — Build tooling and UI framework
- **Tailwind CSS** — Utility-first styling with dark mode support
- **shadcn/ui** — Pre-built accessible components (`Table`, `Sheet`, `Dialog`, `Badge`, `Slider`, `Select`, `Checkbox`, `Textarea`, `Button`)
- **TanStack Query** (`@tanstack/react-query`) — Data fetching, caching, background refetch on scrape completion
- **TanStack Table** (`@tanstack/react-table`) — Sortable, filterable table logic

## Dev Tools
- **`uv`** — Fast Python package/environment manager (recommended over pip/venv)
- **`ruff`** — Python linting and formatting
- **`pytest`** + **`pytest-asyncio`** — Async-capable test runner
