# JuggFinder

**Local freelance lead generator for Boise, Idaho.**

JuggFinder automatically finds small businesses in your area with poor web presence — no website, no HTTPS, outdated design, or no mobile support — and ranks them by how likely they are to pay for a redesign. It gives you a filterable dashboard, AI-drafted outreach messages, and a CSV export so you can start pitching immediately.

---

## How it works

```
Google Maps  →  Website Evaluator  →  AI Scorer  →  Lead Scorer  →  SQLite DB
   (scraper)        (Playwright/httpx)   (Gemini/Groq)  (rubric)      (FastAPI)
                                                                           ↓
                                                                    React Dashboard
```

1. **Scraper** — Playwright drives a headless Chromium browser to search Google Maps for businesses across 13 configurable categories (dentists, HVAC, plumbers, restaurants, etc.) in the configured location.
2. **Evaluator** — For each business's website, JuggFinder checks SSL, mobile viewport, HTTP status code, copyright year, tech stack, and extracts a contact email.
3. **AI Scorer** — The cleaned HTML is sent to **Gemini 2.0 Flash** (primary) or **Groq Llama 3.3 70B** (fallback) to get a 1–10 website quality score plus a list of detected issues.
4. **Lead Scorer** — A deterministic rubric combines website signals, AI score, review count, star rating, and business category into a **lead score (1–10)** and a finer **opportunity score (0–100)** used for ranking.
5. **Dashboard** — A React frontend lets you filter, sort, rescan, update status, take notes, generate AI outreach drafts, and export leads to CSV.

---

## Tech stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Web framework | FastAPI + Uvicorn |
| Browser automation | Playwright (async, Chromium) |
| Database | SQLite via SQLAlchemy 2 + aiosqlite |
| Scheduling | APScheduler (async cron) |
| AI — primary | Google Gemini 2.0 Flash (`google-genai`) |
| AI — fallback | Groq Llama 3.3 70B (`groq`) |
| HTTP client | httpx (async) |
| Retry logic | Tenacity |
| Config | Pydantic Settings + python-dotenv |
| Frontend | React 19 + TypeScript + Vite |
| UI components | shadcn/ui + Base UI + Tailwind CSS v4 |
| Data fetching | TanStack Query v5 |
| Table | TanStack Table v8 |
| Linter | Ruff |
| Tests | pytest + pytest-asyncio |

---

## Repository structure

```
JuggFinder/
├── src/
│   ├── main.py              # FastAPI app, CORS, scheduler, lifespan
│   ├── pipeline.py          # Scrape orchestration, concurrency lock, rescan
│   ├── api/
│   │   ├── routes/
│   │   │   ├── leads.py     # CRUD, export, rescan, outreach draft
│   │   │   └── scrape.py    # POST /scrape/start, GET /scrape/status
│   │   └── schemas.py       # Pydantic request/response models
│   ├── config/
│   │   ├── categories.py    # 13 target categories + payout multipliers
│   │   └── settings.py      # Environment-driven settings (Pydantic)
│   ├── db/
│   │   ├── models.py        # Lead SQLAlchemy model (30+ fields)
│   │   └── session.py       # Async session factory, schema migrations
│   ├── scraper/
│   │   ├── maps.py          # Google Maps Playwright scraper + dedup
│   │   └── evaluator.py     # Website signal extractor (SSL, mobile, etc.)
│   ├── scorer/
│   │   ├── ai.py            # Gemini/Groq scoring with rate-limit fallback
│   │   ├── lead.py          # Deterministic lead_score + opportunity_score
│   │   └── outreach.py      # AI outreach draft generator
│   └── utils/
│       └── logging.py       # Structured logger factory
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── Dashboard.tsx       # Top-level layout
│       │   ├── LeadTable.tsx       # Sortable, paginated table
│       │   ├── LeadDetailSheet.tsx # Slide-out panel with full lead info
│       │   ├── FilterBar.tsx       # Search, category, score, status filters
│       │   ├── ScrapeModal.tsx     # Trigger manual scrape, live progress
│       │   ├── StatsBar.tsx        # Total leads, new today, avg score
│       │   └── TopNav.tsx          # App header
│       ├── api/                    # Typed fetch helpers (TanStack Query)
│       ├── hooks/                  # Custom React hooks
│       ├── types.ts                # Shared TypeScript types
│       └── main.tsx                # React entry point
├── tests/
│   ├── test_ai_scorer.py
│   ├── test_dedup.py
│   ├── test_evaluator.py
│   ├── test_lead_scorer.py
│   └── test_maps_helpers.py
├── .env.example             # Template for required environment variables
└── pyproject.toml           # Python project metadata + Ruff + pytest config
```

---

## Getting started

### Prerequisites

- Python 3.12+
- Node.js 18+ (for the frontend)
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)
- A [Groq API key](https://console.groq.com/) (free tier, used as fallback)

### 1. Clone and set up Python environment

```bash
git clone https://github.com/kikiluvv/JuggFinder.git
cd JuggFinder

# Install uv if you don't have it (https://docs.astral.sh/uv/)
pip install uv

# Create venv and install dependencies
uv sync

# Install Playwright's Chromium browser
uv run playwright install chromium
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in at minimum:

```env
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

Other options (all have sensible defaults):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model name |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `DATABASE_URL` | `sqlite+aiosqlite:///./leads.db` | Database connection string |
| `SCRAPE_SCHEDULE_TIME` | `03:00` | Daily auto-scrape time (HH:MM, 24-hr) |
| `SCRAPE_LOCATION` | `Boise Idaho` | Geographic anchor for Maps searches |
| `SCRAPE_MAX_RESULTS` | `60` | Max listings per category per run |
| `SCRAPE_HEADLESS` | `true` | Set `false` to watch the browser |
| `LOG_LEVEL` | `INFO` | Log verbosity |

### 3. Start the backend

```bash
uv run uvicorn src.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running a scrape

### From the dashboard

Click **"Start Scrape"** in the top navigation, choose which categories to include (or select all), and click **Start**. A live progress bar shows the current category and how many leads have been found.

### From the API

```bash
# Scrape all categories
curl -X POST http://localhost:8000/scrape/start \
     -H "Content-Type: application/json" \
     -d '{"categories": ["all"]}'

# Scrape specific categories
curl -X POST http://localhost:8000/scrape/start \
     -H "Content-Type: application/json" \
     -d '{"categories": ["dentist", "HVAC", "plumbers"]}'

# Check live progress
curl http://localhost:8000/scrape/status
```

### Scheduled scrapes

The backend automatically schedules a daily scrape at `SCRAPE_SCHEDULE_TIME`. It uses APScheduler's cron trigger and skips gracefully if a scrape is already running.

---

## Lead scoring

Every lead gets two numeric scores:

### `lead_score` (1–10, display bucket)

| Score | Meaning |
|---|---|
| 10 | No website at all |
| 9 | Website is a social/directory/booking page |
| 8 | Website returns 4xx or 5xx error |
| 7 | No HTTPS |
| 6 | No mobile viewport |
| 5 | AI score ≤ 4 (clearly outdated or broken) |
| 3 | AI score 5–6 (mediocre site) |
| 2 | AI score ≥ 7 (decent site, still an upsell candidate) |
| 1 | Well-established business (≥50 reviews, ≥4.3★, good site) — not worth pitching |

### `opportunity_score` (0–100, ranking composite)

Combines `lead_score` with:
- Copyright year staleness (+15 if ≥5 years old)
- Contact reachability (phone + email presence)
- Google photo count
- Unclaimed Google Business Profile
- Review count confidence multiplier
- Star rating multiplier
- **Category payout multiplier** — dentists and HVAC score higher than restaurants because they pay more for web work

---

## API reference

### Leads

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/leads` | List leads (paginated, filterable, sortable) |
| `GET` | `/leads/stats` | Total, new today, average score |
| `GET` | `/leads/export.csv` | CSV export matching active filters |
| `GET` | `/leads/{id}` | Full lead detail |
| `PATCH` | `/leads/{id}` | Update status, notes, or outreach draft |
| `DELETE` | `/leads/{id}` | Delete a lead |
| `POST` | `/leads/{id}/rescan` | Re-run evaluator + AI scorer |
| `POST` | `/leads/{id}/draft-outreach` | Generate AI cold-outreach message |

### Scrape

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scrape/start` | Start a scrape (runs in background) |
| `GET` | `/scrape/status` | Live progress and selector health |
| `GET` | `/categories` | List available scrape categories |

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` |

---

## Development

### Run tests

```bash
uv run pytest
```

### Lint

```bash
uv run ruff check .
uv run ruff format .
```

### Frontend lint

```bash
cd frontend
npm run lint
```

### Build frontend for production

```bash
cd frontend
npm run build
```

---

## Target categories

The scraper searches 13 business categories by default, each with a payout multiplier that influences opportunity scoring:

| Category | Multiplier |
|---|---|
| Dentist | 1.5× |
| Chiropractor | 1.4× |
| HVAC | 1.4× |
| Plumbers | 1.4× |
| Electricians | 1.3× |
| Contractors | 1.3× |
| Auto repair | 1.15× |
| Landscaping | 1.1× |
| Cleaning services | 1.0× |
| Hair salon | 1.0× |
| Pet grooming | 0.95× |
| Local retail | 0.95× |
| Restaurants | 0.85× |

To add or change categories, edit `src/config/categories.py`.

---

## AI providers

JuggFinder uses AI in two places:

1. **Website scoring** (`src/scorer/ai.py`) — Rates the scraped HTML 1–10 and lists detected issues. Gemini is used first; if it hits a rate limit it waits 60 seconds and retries once, then switches to Groq for the rest of the session.

2. **Outreach drafting** (`src/scorer/outreach.py`) — Generates a short, personalized cold-email referencing a specific signal (no HTTPS, outdated copyright, broken link, etc.). Triggered on-demand from the dashboard, not during the scrape, to preserve API quota.

Model names are configurable in `.env` so you can swap models without code changes when vendors deprecate them.
