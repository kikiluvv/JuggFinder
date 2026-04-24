# JuggFinder — Development Phases Index

Build order is strictly sequential. Each phase must be complete and verified before starting the next. Do not skip ahead.

---

## Phase Overview

| Phase | Name | Primary Concern |
|---|---|---|
| [01](./PHASE_01_PROJECT_SETUP.md) | Project Setup & Scaffolding | Repo layout, tooling, env, dependencies |
| [02](./PHASE_02_DATABASE.md) | Database Layer | SQLAlchemy models, schema, async session |
| [03](./PHASE_03_CONFIG.md) | Config & Categories | `.env` loading, category list, constants |
| [04](./PHASE_04_SCRAPER.md) | Google Maps Scraper | Playwright discovery, dedup, rate limiting |
| [05](./PHASE_05_EVALUATOR.md) | Website Evaluator | httpx fetching, SSL/mobile/status checks |
| [06](./PHASE_06_AI_SCORER.md) | AI Scoring | Gemini primary, Groq fallback, null-safe |
| [07](./PHASE_07_LEAD_SCORER.md) | Lead Scorer | Rubric-based composite score (1–10) |
| [08](./PHASE_08_PIPELINE.md) | Scraper Pipeline | Wire stages 1–4 into a single async pipeline |
| [09](./PHASE_09_API.md) | FastAPI Backend | All REST endpoints + BackgroundTask scrape |
| [10](./PHASE_10_SCHEDULER.md) | APScheduler Integration | Daily job, concurrency lock, lifespan hook |
| [11](./PHASE_11_FRONTEND_SETUP.md) | Frontend Setup | Vite + React + TS + Tailwind + shadcn/ui |
| [12](./PHASE_12_FRONTEND_CORE.md) | Frontend Core Components | Stats bar, lead table, filters, search |
| [13](./PHASE_13_FRONTEND_PANELS.md) | Frontend Panels & Modals | Side drawer detail, Scrape Now modal |
| [14](./PHASE_14_INTEGRATION.md) | End-to-End Integration | Run full pipeline, verify data in dashboard |

---

## Hard Rules During Development

- Never start a new phase if the previous phase has unresolved errors.
- Never add a dependency not listed in `TECH_STACK.md` without a clear reason.
- All Python I/O must be `async`. No blocking calls.
- All secrets go in `.env`. Never hardcode keys.
- Run `ruff check` and `ruff format` before considering any Python file done.
- Use `uv` for all Python package operations, not `pip`.
