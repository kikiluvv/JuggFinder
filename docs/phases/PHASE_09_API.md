# Phase 09 — FastAPI Backend

## Goal
Expose all data and pipeline controls via a REST API. The frontend consumes this exclusively — no other communication channel exists.

## Completion Criteria
- [ ] All 8 endpoints implemented and returning correct shapes
- [ ] Pydantic schemas defined for all request/response bodies
- [ ] `PATCH /leads/{id}` only allows updating `status` and `notes`
- [ ] `POST /scrape/start` runs the pipeline as a `BackgroundTask` and returns immediately
- [ ] `GET /scrape/status` reflects live state from `_scrape_state` in `pipeline.py`
- [ ] CORS enabled for `localhost:5173`
- [ ] All DB queries use `async with SessionLocal()` — no sync calls

---

## Endpoints

### Leads

```
GET  /leads
  Query params:
    - search: str (optional) — filter name or address
    - category: list[str] (optional, multi)
    - status: list[str] (optional, multi)
    - score_min: int (default 1)
    - score_max: int (default 10)
    - has_website: "all" | "yes" | "no" | "social" (default "all")
    - sort_by: "lead_score" | "created_at" | "name" | "category" (default "lead_score")
    - sort_dir: "asc" | "desc" (default "desc")
    - page: int (default 1)
    - page_size: int (default 50)
  Returns: { leads: LeadSummary[], total: int, page: int, pages: int }

GET  /leads/stats
  Returns: { total: int, new_today: int, avg_score: float }

GET  /leads/{id}
  Returns: LeadDetail

PATCH /leads/{id}
  Body: { status?: str, notes?: str }
  Returns: LeadDetail

DELETE /leads/{id}
  Returns: { ok: true }
```

### Scrape

```
POST /scrape/start
  Body: { categories: ["all"] | ["cat1", "cat2", ...] }
  Returns: { ok: true, message: str }
  — If already running: 409 with { detail: "Scrape already in progress" }

GET  /scrape/status
  Returns: { running: bool, started_at: str | null, categories: list[str] }

GET  /categories
  Returns: { categories: list[str] }
```

---

## Pydantic Schemas (`src/api/schemas.py`)

Define:
- `LeadSummary` — fields for the table view (id, name, category, lead_score, website_url, status, created_at)
- `LeadDetail` — all fields including AI fields, ai_issues deserialized from JSON string to list
- `LeadUpdate` — `status: str | None`, `notes: str | None` (both optional)
- `ScrapeStartRequest` — `categories: list[str]`
- `StatsResponse` — `total`, `new_today`, `avg_score`

---

## CORS Setup

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Route Structure

```
src/api/routes/leads.py   — all /leads/* routes
src/api/routes/scrape.py  — /scrape/start, /scrape/status, /categories
```

Include both routers in `src/main.py` with `app.include_router(...)`.

---

## Done When
All endpoints return correct data when tested via Swagger UI at `localhost:8000/docs`. `POST /scrape/start` triggers a background scrape and `GET /scrape/status` shows `running: true` while it runs.
