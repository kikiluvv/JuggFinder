# Integration Logic

## Data Flow

```
Scrape Trigger (APScheduler daily job OR manual POST /scrape/start)
    │
    ├─> Scheduled: all categories
    └─> Manual: user-selected categories (1, many, or all)
            │
            ▼
    Google Maps (Playwright)
        └─> Business record (name, address, phone, URL, rating, reviews, place_id)
                └─> Dedup check: skip if place_id or (name + address) already in DB
                        │
                        ▼
                Website Evaluator (httpx)
                        ├─> No URL? → early score 10, skip AI, write to DB
                        ├─> URL is social/directory/booking? → early score 9, skip AI, write to DB
                        ├─> URL returns 4xx/5xx? → early score 8, skip AI, write to DB
                        └─> URL is a real website:
                                ├─> HTTPS check (SSL?)
                                ├─> Mobile check (<meta name="viewport">?)
                                ├─> Copyright year scan (footer text)
                                ├─> Email extraction (homepage + contact/about path)
                                ├─> Tech-stack detection (Wix/WordPress/Squarespace/etc.)
                                └─> Gemini 2.0 Flash → quality score + issues + summary
                                        │ (fallback: Groq Llama 3 on rate limit)
                                        ▼
                                Scorer (src/scorer/)
                                        ├─> lead_score (1–10)
                                        └─> opportunity_score (0–100)
                                                └─> SQLite (leads.db)
```

---

## Lead Scoring Rubric

Applied in priority order — first matching condition wins.

| Condition | Lead Score |
|---|---|
| No website URL at all | **10** |
| URL is social / directory / booking placeholder | **9** |
| Website returns 4xx or 5xx HTTP status | **8** |
| Website exists but no HTTPS | **7** |
| Website has no mobile viewport meta tag | **6** |
| Website is outdated — AI score ≤ 4 | **5** |
| Website is mediocre — AI score 5–6 | **3** |
| Website is decent — AI score ≥ 7 | **2** |
| Override: AI ≥ 7 AND reviews ≥ 50 AND rating ≥ 4.3 | **1** |

`opportunity_score` then refines ranking with review confidence, rating, category payout multiplier, copyright-age signal, contact reachability, and listing quality signals.

---

## AI Prompting Strategy

### Website Quality Prompt (Gemini 2.0 Flash / Groq Llama 3)
```
You are evaluating a small business website to determine if it needs a professional redesign.
Analyze the following HTML content and return ONLY a valid JSON object — no explanation, no markdown.

HTML snippet (truncated to 3000 chars):
{html_snippet}

Respond with exactly this JSON format:
{
  "score": <integer 1-10>,
  "issues": ["<issue1>", "<issue2>", ...],
  "summary": "<one sentence describing the website quality>"
}

Scoring guide:
10 = modern, fast, mobile-friendly, professional design
 7 = functional but visually dated or lacking polish
 5 = clearly outdated, not mobile-friendly, or unprofessional
 3 = barely functional, very old design
 1 = broken, nearly non-existent, or completely unusable
```

### AI Fallback Chain
1. Call **Gemini 2.0 Flash** (primary)
2. On `429 ResourceExhausted` → wait 60 seconds, retry once
3. If still failing → switch to **Groq (Llama 3)** for the remainder of the session
4. If Groq also fails → log the error, store `ai_score = null`, `ai_issues = []`, `ai_summary = null`, continue pipeline without blocking

---

## Scrape Trigger Modes

### Scheduled (Daily — All Categories)
- Fired automatically by APScheduler at the configured time (default 3 AM)
- Passes the full `CATEGORIES` list to the scraper
- Skips businesses already in the database (idempotent)

### Manual — Via Dashboard
- User clicks "Scrape Now" and selects categories in the modal
- Frontend sends `POST /scrape/start` with a `categories` array
- Accepted values: `["all"]` OR an array of specific category names matching those in `src/config/categories.py`
- If `"all"` is passed, the backend resolves it to the full category list

```json
// Examples:
{ "categories": ["all"] }
{ "categories": ["restaurants", "plumbers"] }
{ "categories": ["hair salon"] }
```

---

## Google Maps Scraping Queries

Queries are assembled from the category config × the fixed location string:
```python
f"{category} Boise Idaho"
```

Examples:
- `"restaurants Boise Idaho"`
- `"plumbers Boise Idaho"`
- `"hair salon Boise Idaho"`

Each query scrapes the Maps sidebar results list, scrolling to load more until either:
- No new results appear, or
- A configurable max is hit (default: 60 results per query)

Sleep between page scrolls: 2–4 seconds (randomized). Sleep between full queries: 10–20 seconds (randomized).

---

## Deduplication

Before inserting, the scraper checks for an existing record matching:
1. `place_id` (Google Maps unique business ID — preferred, most reliable)
2. Fallback: `name + address` exact match (if place_id not available)

If a match is found, the business is skipped entirely. This makes every scrape run safe to re-run without creating duplicates.

---

## Lead Status Workflow

Statuses are managed exclusively in the dashboard. The scraper always creates new records as `new`.

| Status | Meaning |
|---|---|
| `new` | Just discovered — highlighted in the UI, not yet reviewed |
| `reviewed` | You've looked at the lead but haven't decided |
| `interested` | You intend to reach out manually |
| `archived` | Not a fit — hidden from the default view |

Transitions are free-form (you can move a lead to any status at any time). Current behavior has no automated status changes. Future inbound-reply triage may suggest status updates, but must remain overrideable.

**Target evolution:** dashboard `status` may remain the human-facing label while a separate **workflow state** (see `docs/CLIENT_LIFECYCLE_AUTOMATION.md`) drives automation — or the two are merged deliberately with a migration plan. Avoid duplicating “truth” in email tables vs lead rows without an **engagement** abstraction.

---

## Client lifecycle workflow (target architecture)

This section summarizes the **north-star pipeline**; it is not fully implemented yet. Full detail: `docs/CLIENT_LIFECYCLE_AUTOMATION.md`.

```
Scrape / qualify
    → contact (draft / gated send; future: job queue)
    → inbound parse + classify (confidence + manual review queue)
    → scope capture (structured spec + optional client form)
    → generate artifact (repo from templates + AI fill)
    → verify (CI, scans, budgets)
    → preview deploy (ephemeral URL)
    → approval + payment gate (hard checkpoint)
    → promote / handoff (production DNS or deliverable package)
```

**Principles:** idempotent jobs, append-only **engagement events**, global and per-lead **pause**, and **no production DNS** until explicit approval (and payment when required).

---

## Outreach Guardrails (Phase B)

Outbound sends are gated by DB-backed policy + suppression checks before SMTP delivery:

- Policy endpoints:
  - `GET /settings/outreach-policy`
  - `PATCH /settings/outreach-policy`
- Suppression endpoints:
  - `GET /settings/outreach-suppressions`
  - `POST /settings/outreach-suppressions`
  - `DELETE /settings/outreach-suppressions/{id}`
- Usage endpoint:
  - `GET /settings/outreach-policy/usage-today`

`POST /leads/{id}/send-outreach` enforces:
- global policy enabled switch
- allowed lead statuses
- send window (HH:MM + timezone)
- daily cap
- suppression list
- do-not-contact note checks

All send attempts are logged with status (`sent`, `failed`, `blocked`) for auditability.

---

## Database Schema (Reference)

```sql
CREATE TABLE leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id    TEXT UNIQUE,
    name        TEXT NOT NULL,
    category    TEXT,
    address     TEXT,
    phone       TEXT,
    website_url TEXT,
    rating      REAL,
    review_count INTEGER,
    has_ssl     BOOLEAN,
    has_mobile_viewport BOOLEAN,
    website_status_code INTEGER,
    copyright_year INTEGER,
    ai_score    INTEGER,
    ai_issues   TEXT,      -- JSON array stored as string
    ai_summary  TEXT,
    lead_score  INTEGER NOT NULL,
    status      TEXT DEFAULT 'new',
    notes       TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Additional outreach tables (not shown in full above):
- `app_settings` (policy key/value pairs)
- `outreach_suppressions` (email suppression list)
- `outreach_send_logs` (send audit log)
