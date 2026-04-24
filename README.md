# JuggFinder

**Local-first lead finder for Boise-area small businesses.** JuggFinder scrapes discovery sources (Google Maps), evaluates each business’s web presence with deterministic checks plus AI scoring, ranks opportunities, and exposes everything through a small **FastAPI** backend and **React** dashboard you run on your own machine.

The goal is practical freelance pipeline work: spend less time hunting and more time talking to owners who actually need help with their site.

---

## What it does

- **Discover** local businesses via category-driven Maps scraping (Boise-focused configuration).
- **Evaluate** websites (or lack thereof): technical signals, content hints, and an AI-assisted quality score.
- **Score** leads with a numeric **lead score** and a complementary **opportunity score** for sorting and filtering.
- **Review** leads in a dashboard: notes, status, and AI-drafted outreach copy.
- **Optional — gated email send:** when enabled, send first-touch email through your SMTP provider with **DB-backed guardrails** (daily caps, send windows, suppression list, allowed statuses) and **send logging** for traceability.

---

## How it works (high level)

1. **Scrape** — Playwright-backed Maps workflow collects candidate businesses for configured categories.
2. **Normalize & dedupe** — Records are merged into SQLite with stable identities.
3. **Evaluate** — Fetches the public site when available; runs heuristics and prepares context for AI.
4. **Score** — Deterministic rubric plus LLM analysis (Gemini primary, Groq/Llama fallback) produce rankings.
5. **Serve** — FastAPI exposes CRUD, scrape control, settings, draft-outreach, and (when configured) send-outreach.
6. **Schedule** — APScheduler can run a daily scrape at a configurable local time.

Interactive API documentation is available at `/docs` when the backend is running.

---

## Repository structure

```
jugg-finder/
├── src/
│   ├── main.py              # FastAPI app, CORS, scheduler wiring
│   ├── pipeline.py          # End-to-end scrape/orchestration
│   ├── api/                 # Routes (leads, scrape, settings) + Pydantic schemas
│   ├── config/              # App settings (env) and category config
│   ├── db/                  # SQLAlchemy models, SQLite session, schema helpers
│   ├── scraper/             # Maps scraping + site evaluation
│   ├── scorer/              # Lead scoring, AI integration, outreach drafting
│   ├── outreach/            # SMTP sender + guardrail/policy helpers
│   └── utils/               # Logging, .env persistence helpers, etc.
├── frontend/                # Vite + React + TypeScript dashboard (Tailwind, shadcn/ui)
├── tests/                   # pytest suite
├── pyproject.toml           # Python deps (uv)
└── .env.example             # Environment template
```

---

## Tech stack

| Layer | Choices |
|--------|---------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async SQLite), APScheduler |
| Frontend | React 18+, TypeScript, Vite, Tailwind CSS, TanStack Query & Table |
| Scraping | Playwright (Chromium) |
| AI | Google Gemini (primary), Groq Llama (fallback) |
| Tooling | uv, ruff, pytest |

---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **[uv](https://docs.astral.sh/uv/)** — install via the site instructions or `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Setup

### 1. Clone and environment

```bash
git clone <your-fork-or-repo-url>
cd jugg-finder
cp .env.example .env
```

Edit `.env` and add at least **`GEMINI_API_KEY`** and **`GROQ_API_KEY`** (see `.env.example` for the full set of options).

### 2. Backend

```bash
uv sync
uv run playwright install chromium
```

### 3. Frontend

```bash
cd frontend && npm install
```

---

## Running locally

**Terminal 1 — API**

```bash
uv run uvicorn src.main:app --reload --port 8000
```

**Terminal 2 — UI**

```bash
cd frontend && npm run dev
```

- **API:** http://localhost:8000  
- **Swagger / OpenAPI:** http://localhost:8000/docs  
- **Dashboard:** http://localhost:5173  

SQLite data is stored locally (default `leads.db` — see `.env.example` if configurable).

---

## Optional: automated outreach (SMTP)

Outreach sending is **off unless** you set `OUTREACH_SEND_ENABLED=true` and valid SMTP credentials. Use a provider-specific app password or SMTP token — never commit secrets.

Typical Gmail / Google Workspace SMTP:

```bash
OUTREACH_SEND_ENABLED=true
OUTREACH_SENDER_NAME="Your Name"
OUTREACH_SENDER_EMAIL="you@example.com"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USERNAME="you@example.com"
SMTP_PASSWORD="your-app-password"
SMTP_USE_TLS=true
```

**Guardrails** (daily cap, send window, suppression list, allowed lead statuses) are stored in the database and can be adjusted from the in-app **Settings** UI once the stack is running. Every send attempt is written to an audit log for blocked, failed, and successful outcomes.

---

## Quality checks

```bash
uv run ruff check src/
uv run ruff format src/
uv run pytest
```

---

## Roadmap / future direction

The long-term aim is a **fully orchestrated client lifecycle** (as little hands-on work as is safe): discover → qualify → contact → parse replies → (optional) voice qualification → **scope → build → verify → preview → approve → deliver**, with **hard gates** for money, legal scope, and production infrastructure.

**Architecture themes** (full blueprint: [`docs/CLIENT_LIFECYCLE_AUTOMATION.md`](docs/CLIENT_LIFECYCLE_AUTOMATION.md)):

1. **State machine + job queue** — stages and **idempotent** jobs (send, classify, generate, deploy) with retries, timeouts, and visible failures — not only synchronous HTTP handlers.
2. **Unified engagement model** — one **thread** per relationship with append-only **events** (outbound, inbound raw, classifications, transcripts, human overrides) across email and future channels.
3. **Confidence-gated AI** — triage and follow-up automation route **low-confidence** results to a **manual review queue**; high-confidence suggestions remain overrideable.
4. **Build pipeline** — structured spec → generated repo/artifact → **automated verification** (tests, scans, budgets) → **ephemeral preview URL** → **logged approval** → promotion (no surprise DNS changes).
5. **Commercial checkpoint** — lightweight terms + **payment/deposit** on the path to production or final handoff, so automation optimizes for revenue and boundaries, not just “shipping.”
6. **Observability + kill switches** — dashboards (volume, block reasons, time-in-stage, override rates) and a **global pause** that stops outbound, calls, and deploys without corrupting data.

**Near-term delivery order:** inbound triage (Phase 17) → workflow backbone → engagement unification → conversation rules → verify/preview → commercial gate → voice last (failures are costliest on the phone).

Principles stay the same: **local-first**, **human-overridable**, **rate-limited and traceable** automation — warm and useful, not spammy.

---

## Security & compliance notes

- This tool can send real email and store business contact data **on your machine**. You are responsible for CAN-SPAM/GDPR-style obligations, accurate sender identity, and honoring unsubscribe / do-not-contact signals.
- Keep `.env` out of version control; rotate API keys and SMTP passwords if exposed.

---

## Contributing

Issues and PRs are welcome. Please run **ruff** and **pytest** before submitting changes.

---

## License

No license file is bundled in this repository yet. Add a `LICENSE` of your choice if you plan to distribute or accept contributions under explicit terms.
