# Phase 01 — Project Setup & Scaffolding

## Goal
Establish the full directory structure, tooling, and dependency files so every subsequent phase has a clean foundation to build on.

## Completion Criteria
- [ ] Directory tree matches the layout below
- [ ] `uv` virtual environment created and all backend dependencies installable
- [ ] `ruff` runs without error on an empty/stub Python file
- [ ] `.env.example` committed; `.env` in `.gitignore`
- [ ] Frontend scaffold (`npm create vite`) boots at `localhost:5173`
- [ ] `README.md` documents how to start both services

---

## Directory Layout

```
jugg-finder/
├── .env                    # secrets (gitignored)
├── .env.example            # template (committed)
├── .gitignore
├── README.md
├── pyproject.toml          # uv/ruff config + dependencies
├── logs/                   # scraper.log goes here (gitignored)
├── docs/
│   └── phases/             # this folder
├── src/
│   ├── main.py             # FastAPI app entry point
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py     # pydantic-settings / dotenv loader
│   │   └── categories.py   # CATEGORIES list
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py       # SQLAlchemy ORM model
│   │   └── session.py      # async engine + SessionLocal
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── maps.py         # Playwright Google Maps scraper
│   │   └── evaluator.py    # httpx website evaluator
│   ├── scorer/
│   │   ├── __init__.py
│   │   ├── ai.py           # Gemini + Groq AI scoring
│   │   └── lead.py         # rubric-based lead_score calculator
│   ├── pipeline.py         # orchestrates scraper → evaluator → scorer → db
│   └── api/
│       ├── __init__.py
│       ├── routes/
│       │   ├── leads.py
│       │   └── scrape.py
│       └── schemas.py      # Pydantic request/response models
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── src/
    │   ├── main.tsx
    │   ├── App.tsx
    │   ├── api/            # TanStack Query hooks
    │   ├── components/     # shadcn/ui + custom components
    │   └── types.ts        # shared TypeScript interfaces
    └── ...
```

---

## Steps

### 1. Initialize Python project
```bash
uv init
uv add fastapi uvicorn sqlalchemy aiosqlite httpx playwright \
       google-generativeai groq apscheduler tenacity python-dotenv
uv add --dev ruff pytest pytest-asyncio
```

### 2. Configure `pyproject.toml`
Add a `[tool.ruff]` section:
```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

### 3. Create `.env.example`
```
GEMINI_API_KEY=
GROQ_API_KEY=
SCRAPE_SCHEDULE_TIME=03:00
DATABASE_URL=sqlite+aiosqlite:///./leads.db
LOG_LEVEL=INFO
```

### 4. Initialize Playwright browsers
```bash
uv run playwright install chromium
```

### 5. Scaffold frontend
```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install @tanstack/react-query @tanstack/react-table
npx shadcn@latest init
```

### 6. Verify both servers start
```bash
# Backend
uv run uvicorn src.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

---

## Done When
Both dev servers run without errors. The `/docs` endpoint on the FastAPI app returns a working Swagger UI.
