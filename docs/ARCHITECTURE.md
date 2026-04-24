# Architecture Overview

JuggFinder is a decoupled lead generation pipeline designed for zero cost and minimal resource footprint. Everything runs locally on your machine via two long-running services: a FastAPI backend and a Vite dev server.

Today, the system is primarily discovery + scoring + **gated outreach**. The **long-term architecture** adds a **client lifecycle orchestration** layer: explicit **states**, **durable jobs**, a unified **engagement** model across channels, **build → verify → preview → release**, and **commercial gates** (approval + payment) before irreversible delivery. See [`docs/CLIENT_LIFECYCLE_AUTOMATION.md`](CLIENT_LIFECYCLE_AUTOMATION.md).

## System Components

```
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI Service                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  APScheduler (in-process)                           │    │
│  │  └─> Daily job @ configurable time (default 3 AM)  │    │
│  │       └─> Scrape ALL categories automatically      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Manual Scrape Endpoint (POST /scrape/start)        │    │
│  │  └─> Accepts: { categories: ["all"] | ["cat1"...] }│    │
│  │  └─> Runs scraper as background task                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  REST API Endpoints                                 │    │
│  │  GET  /leads          — list with filter/sort/search│    │
│  │  GET  /leads/{id}     — single lead detail          │    │
│  │  PATCH /leads/{id}    — update status or notes      │    │
│  │  DELETE /leads/{id}   — remove a lead               │    │
│  │  GET  /scrape/status  — is a scrape running?        │    │
│  │  GET  /categories     — list of configured targets  │    │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │  SQLite DB     │  (leads.db — local file)
                   │  (SQLAlchemy   │
                   │  + aiosqlite)  │
                   └────────────────┘
                            ▲
┌──────────────────────────────────────────────────────────────┐
│                  Scraper Pipeline                            │
│                                                              │
│  Stage 1: Discovery (Playwright → Google Maps)               │
│    └─> name, address, phone, website URL, rating, reviews   │
│    └─> Dedup check → skip if already in DB                  │
│                                                              │
│  Stage 2: Evaluation (httpx → business website)             │
│    ├─> No website URL? → score 10, skip AI call             │
│    ├─> URL is social/Yelp? → score 9, skip AI call          │
│    └─> Has website? → SSL, mobile check, HTML age signals   │
│           └─> Gemini 2.0 Flash (primary) or Groq (fallback) │
│                                                              │
│  Stage 3: Scoring (src/scorer/)                             │
│    └─> Composite lead score (1–10) stored to DB             │
└──────────────────────────────────────────────────────────────┘
                            ▲
                            │ triggers (scheduled or manual)
                            │
┌──────────────────────────────────────────────────────────────┐
│              React Dashboard (Vite + Tailwind)               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Stats Bar: Total Leads | New Today | Avg Score     │    │
│  │             | Scraping In Progress indicator        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Lead Table / List                                  │    │
│  │  - Color-coded by status (New = highlighted)        │    │
│  │  - Sortable columns: Score, Date Found, Name, Cat.  │    │
│  │  - Filters: Category, Status, Score range, Website  │    │
│  │  - Search: by name or address                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Lead Detail Panel (side drawer)                    │    │
│  │  - Full business info, AI score + issues            │    │
│  │  - Status dropdown, Notes textarea                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  "Scrape Now" Button → Category Selection Modal     │    │
│  │  - All / individual category checkboxes            │    │
│  │  - Progress feedback while running                  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Scheduling Logic
- **APScheduler** runs inside the FastAPI process (no external cron needed).
- When the FastAPI server starts, the scheduler registers a daily job.
- The daily job runs at a configurable time (set in `.env`, default `03:00`).
- The job only fires if the service is running — there is no system-level scheduling dependency.
- The same scraper function is used for both scheduled and manual runs; the only difference is the category list passed to it.

## Scraper Trigger Modes
| Mode | Categories | Triggered By |
|---|---|---|
| Scheduled (daily) | All categories | APScheduler (auto) |
| Manual — All | All categories | Dashboard "Scrape Now" → select all |
| Manual — Subset | 1 or more selected | Dashboard "Scrape Now" → pick categories |

## Data Layer
- Single local SQLite file: `leads.db`
- Managed via SQLAlchemy (async, using `aiosqlite`)
- Schema: business metadata, website health signals, AI score + issues, lead score, status, notes, timestamps.

## Lead Status Workflow (today)
`New` → `Reviewed` → `Interested` → `Archived`
Status is set manually in the dashboard. The scraper always creates new records as `new`.

## Target lifecycle orchestration (roadmap)
Not all of this exists in code yet; it guides evolution alongside `CLIENT_LIFECYCLE_AUTOMATION.md`.

- **State machine:** lead/client progresses through stages such as `discovered` → `qualified` → `contacted` → `replied` → `scoped` → `building` → `preview_sent` → `approved` → `deployed` / `archived`, with explicit transition rules.
- **Job queue:** idempotent jobs (`send_first_touch`, `parse_inbound`, `classify_reply`, `generate_site`, `verify_build`, `deploy_preview`, `promote_production`) with retries, timeouts, and dead-letter visibility.
- **Engagement model:** append-only **events** per thread (email today; voice/transcripts later) so outbound, inbound, classifications, and overrides share one audit trail.
- **Build pipeline:** structured scope → generated artifact (repo) → automated checks → ephemeral preview → human/client **approval** → promotion.
- **Kill switches:** global pause plus per-lead pause; extends current outreach enable/cap philosophy to calls and deploys.

## Outreach Capability Layers

### Layer 1 (Implemented): Draft Assist
- Endpoint: `POST /leads/{id}/draft-outreach`
- Purpose: generate a short personalized first-touch draft from lead signals.
- Human remains sender of record.

### Layer 2 (Implemented): Gated Auto-Send
- Endpoint: `POST /leads/{id}/send-outreach`
- Enforced controls: enabled switch, daily cap, send window + timezone, allowed lead statuses, suppression list.
- Policy source: DB-backed settings table (`app_settings`) editable via settings endpoints/UI.
- Delivery telemetry: `outreach_send_logs` with `sent|failed|blocked`.

### Layer 3 (Planned): Inbound AI Triage
- Parse inbound messages and classify intent:
  `interested`, `not now`, `not interested`, `wrong contact`, `unsubscribe`.
- Auto-apply safe actions (labeling, reminders) when confidence is high.
- Route ambiguous cases to manual review.

### Layer 4 (Future): AI Call Representative
- Handles first-touch qualification calls only.
- Must self-identify, capture transcript, and hand off to human when uncertain.
- Never makes legal/financial promises.

### Layer 5 (Future): Build, verify, preview, release
- Structured **scope** capture (DB/JSON) from triage + optional client inputs.
- **Generator** produces a repo or deployable artifact from templates + AI-assisted fill.
- **Verification** job: lint/tests, link checks, performance/a11y budgets as configured.
- **Preview** deploy to ephemeral URL; **no production DNS** until approval.
- **Promotion** only after logged approval and (when required) **payment** state.

### Layer 6 (Future): Commercial / legal checkpoint
- Lightweight contracts or terms acceptance, invoicing/deposit (e.g. Stripe), IP/handoff checklist tied to state transitions.

## Compliance and Safety Envelope
- Outreach is polite and non-deceptive.
- Do-not-contact and unsubscribe handling is mandatory on **every outbound channel**.
- All automation must be reversible, auditable, and manually overrideable.
- **Hard gates** (payments, production DNS, binding scope) are never silently skipped for convenience.

## Configuration Surfaces
- **Env-backed (UI editable via `/settings`):** SMTP credentials, sender identity, base send enable flag.
- **DB-backed (UI editable via outreach policy settings):** daily caps, send windows, suppression enforcement, allowed statuses.
