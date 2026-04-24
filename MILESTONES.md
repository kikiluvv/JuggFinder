# JuggFinder — Milestones

## Current Phase: 17 — Engagement & Inbound Triage 🔄

**Milestone tracking:** [`docs/phases/PHASE_17_ENGAGEMENT_AND_INBOUND.md`](docs/phases/PHASE_17_ENGAGEMENT_AND_INBOUND.md)

| Milestone | Focus | Status |
|-----------|--------|--------|
| **17.1** | `engagements` + `engagement_events`, dual-write from send-outreach, `GET /leads/{id}/engagement`, Activity UI | ✅ Done |
| **17.2** | `POST /leads/{id}/inbound` + dev `POST /dev/pipeline-dry-run` (env-guarded), tests for TEST BUSINESS | ✅ Done |
| **17.3** | LLM classify + confidence, review queue, human override events | Planned |

---

| Phase | Status | Completed |
|---|---|---|
| 01 — Project Setup & Scaffolding | ✅ Done | 2026-04-21 |
| 02 — Database Layer | ✅ Done | 2026-04-21 |
| 03 — Config & Categories | ✅ Done | 2026-04-21 |
| 04 — Google Maps Scraper | ✅ Done | 2026-04-21 |
| 05 — Website Evaluator | ✅ Done | 2026-04-21 |
| 06 — AI Scoring | ✅ Done | 2026-04-21 |
| 07 — Lead Scorer | ✅ Done | 2026-04-21 |
| 08 — Scraper Pipeline | ✅ Done | 2026-04-21 |
| 09 — FastAPI Backend | ✅ Done | 2026-04-21 |
| 10 — APScheduler Integration | ✅ Done | 2026-04-21 |
| 11 — Frontend Setup | ✅ Done | 2026-04-21 |
| 12 — Frontend Core Components | ✅ Done | 2026-04-21 |
| 13 — Frontend Panels & Modals | ✅ Done | 2026-04-21 |
| 14 — End-to-End Integration | ✅ Done | 2026-04-21 |
| 15 — Scraping & Scoring Hardening | ✅ Done | 2026-04-21 |
| 16 — Outreach Phase B Guardrails | ✅ Done | 2026-04-23 |
| 17 — Engagement & Inbound Triage | 🔄 In Progress | — |

---

## Long-range roadmap (planned — sequencing)

Aligned with `docs/CLIENT_LIFECYCLE_AUTOMATION.md` and outreach Phases F–I. Dates TBD; order matters more than calendar.

| Phase | Name | Objective |
|------|------|-------------|
| 18 | Workflow backbone | Explicit `WorkflowRun` / `WorkflowEvent` (or equivalent), idempotent jobs, stuck/dead-letter visibility in UI |
| 19 | Engagement unification | Deepen `Engagement`/`EngagementEvent` (started in 17.1); optional consolidation vs `outreach_send_logs` only |
| 20 | Conversation + build handoff | Cooldown/max-touch rules; structured **scope** capture from triage + client form |
| 21 | Verify + preview | Generator → CI/link/a11y checks → ephemeral preview URL; no prod DNS |
| 22 | Commercial + release gate | Logged approval + payment/deposit before promote; handoff package |

Voice agent (roadmap Phase E) slots **after** email + triage + build loop are trustworthy — amplified failure modes on phone.

---

## Phase Notes

### Phase 17.2 — Inbound capture + dev dry-run ✅
- `POST /leads/{id}/inbound` → `inbound_received` engagement event; body capped at 16k chars; `GET /leads/{id}/engagement` unchanged.
- `record_inbound_received` in `src/engagement/service.py`.
- Settings: `dev_pipeline_dry_run_enabled`, `dev_pipeline_test_business_name`, `dev_pipeline_test_email`; `.env.example` documented.
- `POST /dev/pipeline-dry-run` (mounted only when flag true): steps `seed` | `draft` | `simulate_outreach_sent` | `simulate_inbound` in canonical order; simulated send sets `payload.dry_run=true` and does **not** write `outreach_send_logs`.
- Frontend: `postLeadInbound` + types; Activity labels `inbound_received`.
- Tests: `tests/test_phase17_2_inbound_and_dry_run.py` (mini FastAPI apps avoid lifespan / real DB during HTTP tests).

### Phase 17.1 — Engagement backbone ✅
- New tables `engagements` (unique `lead_id` + `channel`) and `engagement_events` (append-only `event_type` + JSON `payload`, optional `outreach_send_log_id`).
- `src/engagement/service.py` — `get_or_create_engagement`, `append_engagement_event`.
- `POST /leads/{id}/send-outreach` dual-writes `outreach_sent`, `outreach_blocked`, and `outreach_failed` timeline events after each corresponding `outreach_send_logs` row (with `flush` for stable FK ids).
- `GET /leads/{id}/engagement` returns newest-first timeline (404 if lead missing).
- Lead detail sheet **Activity** block + `fetchLeadEngagement`; send success invalidates engagement query.
- Tests: `tests/test_engagement.py`.

### Phase 16 — Outreach Phase B Guardrails ✅
- Added DB-backed outreach policy (`app_settings`) with configurable controls: enabled switch, daily cap, send window/timezone, suppression toggle, allowed lead statuses.
- Added suppression list table + API endpoints for add/list/delete.
- Added outbound send logging table (`outreach_send_logs`) and wired `send-outreach` to write `sent`, `failed`, and `blocked` events.
- `POST /leads/{id}/send-outreach` now enforces policy checks (window, cap, status allowlist, suppression, do-not-contact notes) before SMTP send.
- Added regression tests for guardrail parsing/window logic/day counting and reran scorer suites.
- Added Settings UI controls for SMTP/env settings + guardrail policy + suppression list management (no manual `.env` editing required for normal operations).
- Handoff note: SMTP dry run is still a developer-only terminal procedure; do not expose it in production UI.

### Phase 15 — Scraping & Scoring Hardening ✅
Post-audit implementation pass. Addresses every P0 and most P1 items in `AUDITS.md`, plus fixes the critical `gemini-1.5-flash` 404 that was silently nulling all AI scores in production. See `CHANGELOG.md` for a line-by-line list with timestamps.

- **Bardenay fix** — well-established businesses (AI score ≥ 7, reviews ≥ 50, rating ≥ 4.3) now floor at `lead_score=1` and drop out of the default view. Prevents wasting outreach time on businesses with solid, loved websites.
- **Opportunity score (0–100)** — new composite metric combining coarse lead score, review confidence, rating, category payout multiplier (dentist 1.5× → restaurant 0.85×), copyright year age, email reachability, unclaimed listings, and photo count. `LeadTable` sorts by this by default.
- **Scraper hardening** — stealth init-script hides `navigator.webdriver`/plugins/languages, modern UA pool rotated per run, Chromium context with `locale=en-US`/`timezone=America/Boise`/Boise geolocation, `--headless=new` mode, CAPTCHA/"sorry" page detection aborts cleanly, per-run `SelectorHealth` counter for drift detection.
- **New data fields** — email (from mailto + contact-page crawl), hours, Google categories, photo count, claimed status, business description, tech stack fingerprint (Wix/Squarespace/WordPress/GoDaddy-builder/Webflow/…), stored in 10 new DB columns via additive `ALTER TABLE` bootstrap (no Alembic needed).
- **AI scoring bulletproofed** — Gemini model env-configurable (default `gemini-2.0-flash`, fixing the 404s observed in Phase 14 logs), JSON schema enforced via `response_schema` (no more markdown-fence parsing), typed `ClientError` rate-limit detection, one 60-s retry before Groq fallback.
- **Outreach drafter** — `POST /leads/{id}/draft-outreach` generates a 2-4 sentence personalized first message from the lead's actual signals. Renders inline in the detail drawer with edit-in-place + copy-to-clipboard.
- **API additions** — `POST /leads/{id}/rescan` (re-evaluates a single lead without a full scrape), `GET /leads/export.csv` (filter-aware CSV download), extended `GET /scrape/status` with category/business progress and selector-health counters.
- **Frontend wins** — live scrape progress bar with `current_category` and `businesses_processed`, Rescan + Draft Outreach buttons per lead, copy-to-clipboard for phone/email/address/draft, Export CSV from the filter bar, default score filter raised to 5+ (payout-focused), new Opportunity column in the table.
- **Caveats** — selector-health counters are logged but not yet alerted; Alembic migrations deliberately deferred (additive-only changes for now); `search` filter still uses `ILIKE`, not FTS.

### Phases 06–13 — Completed in one autonomous session ✅

#### Phase 06 — AI Scoring
- `score_with_ai(html_snippet)` returns `{score, issues, summary}` or null equivalents — never raises
- Uses `google-genai` (new SDK, replacing deprecated `google-generativeai`)
- Session-level `_use_groq_fallback` flag: once Gemini 429s, all subsequent calls in the run go to Groq
- `parse_ai_response()` strips markdown fences, validates score 1–10 range, handles garbage input
- **Tests: 172/172 passed** — 24 new AI scorer tests (parse + fallback state machine)
- `reset_session()` exported for clean test isolation

#### Phase 07 — Lead Scorer
- `calculate_lead_score()` is a pure function — no I/O, no async
- Implements rubric in strict priority order: 10 → 9 → 8 → 7 → 6 → 5 → 3 → 1
- Falls back to `3` when AI score is unavailable (site passes basic checks, assume mediocre)
- Never raises — defaults to `3` on any exception
- **Tests: 28 new tests** — every rubric row, priority ordering, all edge cases verified
- Return type always `int` in 1–10 range, validated across all code paths

#### Phase 08 — Scraper Pipeline
- `run_scrape(categories)` is the single public function called by both scheduler and API
- `asyncio.Lock` prevents concurrent scrape runs; raises `RuntimeError` if already running
- `_scrape_state` dict is the live source of truth for `GET /scrape/status`
- One Playwright Chromium instance per run; closed in `finally` block
- `_process_business()` handles eval → AI → score → DB write; rolls back on error
- `reset_session()` called at start of each run (fresh Gemini/Groq fallback state)
- `"all"` shortcut resolves to full `CATEGORIES` list
- Politeness delay: `random.uniform(10, 20)` seconds between categories

#### Phase 09 — FastAPI Backend
- 8 endpoints: `GET/PATCH/DELETE /leads/{id}`, `GET /leads`, `GET /leads/stats`, `POST /scrape/start`, `GET /scrape/status`, `GET /categories`
- `LeadSummary` / `LeadDetail` / `LeadUpdate` / `ScrapeStartRequest` Pydantic schemas
- `GET /leads` supports: search, category (multi), status (multi), score range, has_website, sort_by, sort_dir, pagination
- `POST /scrape/start` returns 409 if already running; runs pipeline as `BackgroundTask`
- All DB queries via `async with SessionLocal()` — fully async
- CORS enabled for `localhost:5173`
- Swagger UI available at `localhost:8000/docs`

#### Phase 10 — APScheduler Integration
- `AsyncIOScheduler` started in the FastAPI `lifespan` context manager
- Daily job fires at time specified by `SCRAPE_SCHEDULE_TIME` in `.env`
- `_scheduled_scrape()` wrapper catches `RuntimeError` if manual scrape is already running
- `misfire_grace_time=3600` — allows up to 1h late start on server restart
- Next fire time logged at startup
- **Live verified**: `GET /categories` and `GET /health` and `GET /scrape/status` all return correct responses

#### Phases 11–13 — Frontend (Setup + Core + Panels)
- Full component tree: `App → Dashboard → TopNav + StatsBar + FilterBar + LeadTable + LeadDetailSheet + ScrapeModal`
- `StatsBar`: polls stats every 30s, scrape status every 5s, animated pulsing indicator while running
- `FilterBar`: search (text), score range (dual-handle slider), status (checkboxes), has_website (select), categories (checkboxes), archived toggle, Clear button
- `LeadTable`: TanStack Table with server-side sort + pagination; color-coded rows by status; score badges red/amber/gray; `placeholderData` for smooth page transitions
- `LeadDetailSheet`: shadcn `Sheet`, full signal grid, AI issues list, AI summary, status dropdown (immediate save), notes textarea (1s debounce auto-save), "Saved ✓" indicator, Archive button
- `ScrapeModal`: shadcn `Dialog`, Select All checkbox, per-category checkboxes, 409 error display, disabled while running
- Auto-refresh: `Dashboard` watches `scrapeStatus.running` transition `true → false` and invalidates leads/stats queries
- **Build: 0 TypeScript errors, 2028 modules, 493KB JS bundle**

---

### Phase 05 — Website Evaluator ✅
- `evaluate_website(url)` returns a consistent 8-key dict on every code path — callers never check the path taken
- Decision tree: no URL → 10, social/directory → 9, HTTP 4xx/5xx → 8, live site → signals + AI
- `is_social_url` covers 13 platforms including Yelp, Thumbtack, Houzz, Nextdoor — subdomain-aware
- `extract_copyright_year` targets `<footer>` first, falls back to full document; handles ©, "Copyright", "(c)"
- `has_mobile_viewport` uses regex on `<meta name="viewport">` — case-insensitive
- `build_full_result` uses the **final redirect URL** for SSL detection (catches http→https redirectors correctly)
- URLs without a scheme automatically get `https://` prepended before fetching
- tenacity retry: 2 attempts, exponential backoff on `TimeoutException` and `ConnectError`
- `html_snippet` capped at 3000 chars for the AI scorer
- **Tests: 127/127 passed** — 69 new evaluator tests (pure helpers + full `evaluate_website` decision tree via `monkeypatch`)
- Audits: `ruff check` 0 errors, `ruff format` 26 files clean

### Phase 04 — Google Maps Scraper ✅
- Two-phase strategy: scroll feed to collect all card hrefs, then navigate to each place URL individually
- Selector banks with ordered fallbacks for every field — resilient to Google class-name churn
- Consent dialog handler for GDPR overlay
- `extract_place_id_from_url` handles both ChIJ (new) and hex (legacy) formats via regex
- `parse_rating` handles decimals, commas (European), and aria-label text
- `parse_review_count` handles plain digits, comma-separated, and abbreviated "1.2K" format
- `is_duplicate()` exported as pure async function: place_id first, name+address fallback
- tenacity retry on `PlaywrightTimeout` (3 attempts, exponential backoff) on all navigations
- All errors caught per-listing — one bad card never crashes the category run
- **Tests: 58/58 passed** — 14 dedup tests (real in-memory SQLite), 44 unit tests for helpers
- Audits: `ruff check` 0 errors, `ruff format` 25 files clean

### Phase 03 — Config & Categories ✅
- `Settings` (pydantic-settings) loads all env vars from `.env` with correct types and defaults
- `gemini_api_key` and `groq_api_key` are required — raise `ValidationError` immediately on startup if missing or empty
- `scrape_schedule_time` validated as `HH:MM` format at startup
- `CATEGORIES` list: 13 Boise business categories, each used to form `"{category} Boise Idaho"` queries
- `get_logger(name)` in `src/utils/logging.py` — file + console handlers, `TimedRotatingFileHandler` (7-day retention)
- Logger wired into `src/main.py` startup/shutdown messages
- Audits: `ruff check` 0 errors, `ruff format` 22 files clean

### Phase 02 — Database Layer ✅
- `Lead` SQLAlchemy ORM model with all 21 fields matching `INTEGRATION.md` schema exactly
- `JsonList` TypeDecorator serializes `ai_issues` list to/from JSON TEXT column
- `place_id` is `UNIQUE` nullable; `lead_score` and `name` are non-nullable
- `created_at` / `updated_at` use `server_default=func.now()` with `onupdate`
- `leads.db` created via `create_all` — schema verified with `sqlite3 .schema`
- Audits: `ruff check` 0 errors, `ruff format --check` 22 files clean

### Phase 01 — Project Setup & Scaffolding ✅
- `uv` installed; all 12 backend Python packages installed into `.venv`
- Playwright Chromium browser downloaded and installed
- Frontend: Vite + React + TypeScript scaffolded; Tailwind CSS v4 via `@tailwindcss/vite`
- shadcn/ui initialized; `Button` component generated; `@/` alias configured
- TanStack Query and TanStack Table installed
- `src/` directory tree and all Python stub files created
- `frontend/src/types.ts` and `frontend/src/api/` stubs created
- `ruff check src/` — 0 errors
- `npm run build` — 0 errors (92 modules)
- FastAPI `GET /health` returns `{"status":"ok"}`
