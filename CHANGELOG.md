# JuggFinder — Changelog

Chronological log of substantive edits. New entries go at the top.
Audit findings live in `AUDITS.md`; phase summaries live in `MILESTONES.md`.

---

## 2026-04-23

### Phase 17.2 — Inbound capture + dev pipeline dry-run

- `POST /leads/{id}/inbound` with `InboundCaptureRequest` → `inbound_received` timeline event (`record_inbound_received`).
- Dev-only `POST /dev/pipeline-dry-run` when `DEV_PIPELINE_DRY_RUN_ENABLED=true`: seeds `dev:juggfinder-test-business` lead (**TEST BUSINESS** / configurable email), optional real AI `draft`, simulated `outreach_sent` (no SMTP, no send log), simulated inbound.
- Settings + `.env.example`: `DEV_PIPELINE_DRY_RUN_ENABLED`, optional `DEV_PIPELINE_TEST_*` overrides.
- Tests: `tests/test_phase17_2_inbound_and_dry_run.py`; frontend API helper + Activity label for inbound.

### Phase 17.1 — Engagement backbone

- Added `engagements` and `engagement_events` tables (`Engagement`, `EngagementEvent` models).
- `POST /leads/{id}/send-outreach` appends timeline events (`outreach_sent`, `outreach_blocked`, `outreach_failed`) alongside `outreach_send_logs`.
- Added `GET /leads/{id}/engagement` for ordered activity timeline.
- Dashboard lead detail: **Activity** section powered by the new endpoint.
- Docs: `docs/phases/PHASE_17_ENGAGEMENT_AND_INBOUND.md`, phase index + milestones milestone table; `docs/INTEGRATION.md` schema note.

### Documentation — client lifecycle automation (north star)

- Added `docs/CLIENT_LIFECYCLE_AUTOMATION.md`: target **state machine**, **job queue**, **engagement model**, **build → verify → preview → release**, **commercial gates**, **observability/kill switches**, and recommended **implementation sequencing**.
- Updated `docs/GOALS.md`, `docs/ARCHITECTURE.md`, `docs/OUTREACH_AUTOMATION_ROADMAP.md` (Phases F–I), `docs/INTEGRATION.md`, `docs/HANDOFF.md`, and `.cursorrules` to match that blueprint.
- Updated `AUDITS.md` (structural P1/P2 follow-ups), `MILESTONES.md` (long-range phases 18–22), and root `README.md` (roadmap section) for GitHub-facing summary.
- **Repo hygiene:** `.gitignore` now allows the `docs/` tree plus `CHANGELOG.md`, `AUDITS.md`, and `MILESTONES.md` to be versioned alongside `README.md` (root `DEV-README.md` remains ignored for machine-local notes).

### Phase 16 — Outreach Guardrails + Settings UI

#### Backend policy, suppression, and send enforcement
- Added DB models for handoff-safe Phase B controls:
  - `AppSetting` (key/value settings table),
  - `OutreachSuppression`,
  - `OutreachSendLog` (`sent|failed|blocked` + audit metadata).
- Added guardrail service in `src/outreach/guardrails.py`:
  - policy defaults + parsing,
  - local-day send counting by timezone,
  - send-window checks (including overnight windows),
  - suppression checks and email normalization.
- Extended `POST /leads/{id}/send-outreach` to enforce:
  - policy enabled switch,
  - allowed lead statuses,
  - send window,
  - daily cap,
  - suppression list,
  - existing note-level do-not-contact checks.
- Added settings endpoints for policy/suppressions:
  - `GET/PATCH /settings/outreach-policy`
  - `GET /settings/outreach-policy/usage-today`
  - `GET/POST/DELETE /settings/outreach-suppressions...`

#### UI settings flow (no manual `.env` editing required)
- Expanded Settings dialog to manage:
  - SMTP/env fields (`OUTREACH_*`, `SMTP_*`),
  - DB-backed outreach guardrail policy,
  - suppression list add/remove.
- Added frontend API client methods for new policy/suppression endpoints.
- Preserved explicit separation:
  - env-backed settings saved via `/settings`,
  - policy/suppressions persisted in DB via dedicated endpoints.

#### Validation and operational checks
- Added `tests/test_outreach_guardrails.py` (policy defaults/overrides, window logic, daily counting).
- Session validation:
  - `uv run ruff check src/ tests/` clean
  - `uv run ruff format src/ --check` clean
  - `npm run build` clean
  - `pytest` subset including outreach + scorer suites passing.
- SMTP dry-run procedure executed in terminal (dev-only, no email sent):
  - `smtp.google.com` timed out from current network,
  - `smtp.gmail.com` succeeded with STARTTLS + login.
  - Recommended host: `smtp.gmail.com` for Gmail app-password auth.

---

## 2026-04-21

### Phase 15 — Scraping & Scoring Hardening

All timestamps Mountain Time (America/Boise). Grouped by file so reviewers can map changes to modules quickly.

#### 20:30 — `src/config/settings.py`
Added env-configurable settings: `scrape_location`, `scrape_max_results`, `scrape_headless`, `scrape_user_agent`, `gemini_model`, `groq_model`. New validator on `scrape_max_results` (1–500). `.env.example` and `.env` updated. This fixes the silent `gemini-1.5-flash` 404 observed in production — new default is `gemini-2.0-flash`.

#### 20:31 — `src/config/categories.py`
Added `CATEGORY_VALUE_MULTIPLIER` map (dentist 1.5×, HVAC 1.4×, restaurant 0.85×, etc.) and `category_multiplier(name)` accessor. Used by the opportunity score.

#### 20:33 — `src/db/models.py`
Added 10 additive columns to `Lead`: `email`, `hours`, `google_categories`, `business_description`, `photo_count`, `is_claimed`, `tech_stack`, `opportunity_score`, `outreach_draft`, `last_scanned_at`. No existing columns touched.

#### 20:34 — `src/db/session.py` (new bootstrap)
Added `ensure_schema()` — runs `create_all()` then `ALTER TABLE ... ADD COLUMN` for each new column only if it's not already present. Idempotent. Avoids bringing in Alembic for a single-file SQLite app.

#### 20:35 — `src/main.py`
Replaced ad-hoc `create_all()` in the lifespan with `await ensure_schema()`.

#### 20:41 — `src/scraper/maps.py` (major rewrite)
- Stealth init-script (hides `navigator.webdriver`, plugins, languages, chrome.runtime).
- Rotating modern UA pool (Chrome 131, Safari 17, Firefox 132).
- `build_context()` helper: Boise locale/timezone/geolocation, viewport 1440×900, permissions.
- `is_captcha_page()` + `CaptchaEncountered` exception bubbled up through the pipeline.
- `_handle_consent()` now runs on the detail page too (not just search).
- New selectors for category chip, hours, description, photo count, claim link.
- `SelectorHealth` dataclass tracks extraction counters per run.
- `extract_place_id_from_url` now handles `GhIJ` variant alongside `ChIJ`/hex.
- `MAX_RESULTS` and `LOCATION` moved to settings.

#### 20:47 — `src/scraper/evaluator.py`
- Expanded `SOCIAL_DOMAINS` from 13 → 30 entries (Vagaro, Square, OpenTable, DoorDash, Booksy, Linktree, Squareup, Weebly, GoDaddy-sites, Framer, etc.).
- New `clean_html_for_ai()` strips `<script>`, `<style>`, `<noscript>`, comments, and collapses whitespace before passing to the AI. Fixes the "AI sees 3kb of bootstrap JS" problem.
- New `extract_emails()` — mailto + plain-text regex with denylist (noreply, sentry.io, .png, etc.).
- New `detect_tech_stack()` — fingerprints Wix, Squarespace, WordPress, Shopify, Webflow, GoDaddy-builder, Duda, WooCommerce, Joomla, Drupal, BigCommerce, Framer, React SPA, Next.js.
- New `_fetch_contact_page()` — tries explicit `<a>` link first, then `/contact`, `/contact-us`, `/about`, etc., max 4 attempts, 6s timeout each. Used for extra emails and footer copyright years.
- `build_full_result()` now returns `email` and `tech_stack` alongside the existing keys.

#### 20:52 — `src/scorer/ai.py`
- `gemini_model` / `groq_model` from settings.
- JSON schema enforced via `GenerateContentConfig(response_mime_type="application/json", response_schema=...)`. Eliminates the "AI wrapped JSON in markdown" failure mode.
- Typed `_is_rate_limit()` checks `genai_errors.ClientError.code == 429` first, substring fallback for unusual wrappers.
- One-shot Gemini retry after 60-s sleep before falling back to Groq (matches the intent of INTEGRATION.md). `GEMINI_RATE_LIMIT_SLEEP` exposed for tests.
- Groq catches `RateLimitError` and `APIError` explicitly.

#### 20:55 — `src/scorer/lead.py`
- `calculate_lead_score` now accepts optional `biz` dict for the well-established override.
- **Bardenay fix**: when AI ≥ 7 AND reviews ≥ 50 AND rating ≥ 4.3 → `lead_score = 1` (skip bucket).
- AI ≥ 7 without the override now returns `2` (upsell candidate), not `1`. Opens room at the bottom for the override.
- New `calculate_opportunity_score(...)` returns 0–100 composite: base from bucket × 10, adjusted by copyright-year age, reachability (phone/email), photo count, unclaimed bonus, review-count confidence multiplier (0.5–1.15), rating multiplier (0.7–1.15), category multiplier (0.85–1.5). Clamped [0, 100].
- All exceptions now logged (`logger.exception`) instead of silently swallowed.

#### 20:58 — `src/scorer/outreach.py` (new)
AI outreach drafter. Reuses `_get_gemini`/`_get_groq`/`_is_rate_limit` from `ai.py`. Builds context from lead's actual signals (missing HTTPS, dated copyright, tech stack, unclaimed, etc.). Temperature 0.6. Never raises.

#### 21:02 — `src/pipeline.py`
- Shared `SelectorHealth` object per run, exposed via `get_scrape_state()`.
- Progress fields: `current_category`, `categories_done`, `categories_total`, `businesses_processed`, `new_leads`, `error`.
- Per-row DB session (`async with SessionLocal()` per lead). Keeps one bad row from killing the whole run.
- Writes all 10 new Phase-15 fields to the `Lead` row.
- `rescan_lead(id)` helper — re-runs evaluator + AI + scorer on an existing lead, preserves status/notes/outreach_draft.
- Launches Chromium with `--headless=new` and `--disable-blink-features=AutomationControlled`.

#### 21:06 — `src/api/schemas.py`
Added every new field to `LeadSummary` and `LeadDetail`. Added `outreach_draft` to `LeadUpdate`. Extended `ScrapeStatusResponse` with progress + selector health + error fields. New `OutreachDraftResponse`.

#### 21:09 — `src/api/routes/leads.py`
- Shared `_apply_filters()` helper used by list + export.
- `GET /leads/export.csv` — respects filter query params, 27 columns including tech stack, google categories, email, opportunity score, last-scanned timestamp.
- `POST /leads/{id}/rescan` — calls `rescan_lead`.
- `POST /leads/{id}/draft-outreach` — calls `draft_outreach`, persists `outreach_draft` field, returns `{lead_id, draft}`. 502 when both providers fail.
- Default sort changed to `opportunity_score` desc.

#### 21:11 — Frontend `src/types.ts`
Added `opportunity_score`, `email`, `phone` to `LeadSummary`. Full new-field list on `LeadDetail`. Extended `ScrapeStatus` with progress fields. New `SelectorHealth` and `OutreachDraftResponse` interfaces.

#### 21:13 — Frontend `src/api/leads.ts`
Added `rescanLead(id)`, `draftOutreach(id)`, `exportLeadsCsvUrl(params)`. `updateLead` now accepts `outreach_draft`.

#### 21:18 — Frontend `src/components/LeadDetailSheet.tsx` (major rewrite)
- Shows email (mailto link), hours, photo count, Google categories, business description, tech stack chips, opportunity score.
- "Rescan site" button (per-lead, with spinner).
- "AI draft outreach" button — shows draft in an editable Textarea with Copy-to-clipboard.
- Copy buttons on address, phone, email, and draft.
- Unclaimed badge in the header.
- Last-scanned date in the footer.

#### 21:21 — Frontend `src/components/StatsBar.tsx`
Live scrape progress bar — `categories_done / categories_total`, businesses processed, new leads count, current category name. Polls every 3 seconds while scraping. Captures & displays CAPTCHA errors from the last run.

#### 21:23 — Frontend `src/components/FilterBar.tsx`
Added Export CSV link that carries current filters as query params.

#### 21:24 — Frontend `src/hooks/useFilters.ts`
Default `scoreMin` raised from 1 to 5 — hides noise (score 1 = well-established, 2 = decent, 3 = mediocre) by default. Matches the payout-focused mission.

#### 21:25 — Frontend `src/components/LeadTable.tsx`
New Opportunity column (`opportunity_score`) with color tiers: red ≥75, amber ≥50, gray below. Default sort by opportunity score.

#### 21:28 — Tests
- `tests/test_lead_scorer.py` — 15 new tests covering the well-established override, the AI-score-7 → 2 change, and the new `calculate_opportunity_score` composite.
- `tests/test_evaluator.py` — updated shape assertions for new `email`/`tech_stack` keys.
- `tests/test_ai_scorer.py` — patched `GEMINI_RATE_LIMIT_SLEEP` to 0, updated call-count expectations for the one-shot retry.
- **Full suite: 181 passed in 12s**, `ruff check` clean, `ruff format --check` clean, `npm run build` clean.
