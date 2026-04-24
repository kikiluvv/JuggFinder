# JuggFinder — Codebase Audit

**Timestamp:** 2026-04-21 19:47 MDT
**Auditor:** Claude (Cursor)
**Scope:** Post-Phase-14 audit focused on scraping hardening, lead scoring, data capture, and minimal-interaction workflow.
**Codebase under review:** `src/`, `frontend/src/`, `docs/`, `MILESTONES.md`

> No code changes were made. This document is findings-only. Items are labeled **[P0]** (critical / blocks payout), **[P1]** (high — do soon), **[P2]** (nice-to-have).

---

## Addendum — 2026-04-21 (post-Phase-15 reality check)

Most original P0 items have now been implemented (stealth hardening, selector health, opportunity score, extra data fields, rescan, CSV export, outreach draft endpoint). Remaining high-value scraping/scoring opportunities are:

1. **[P1] Dedup normalization pass.** Name/address fallback dedup is exact-match only; normalize whitespace/abbreviations to reduce near-duplicate inserts.
2. **[P1] Contact-page fetch resiliency.** `_fetch_contact_page()` currently does short best-effort requests without tenacity retry; transient failures can hide reachable emails.
3. **[P1] Scoring test guard for low-rating penalty tiers.** Ensure `<3.0` businesses always receive a stronger dampener than `3.0-3.49`.
4. **[P1] Selector-health alerting.** Counters are surfaced, but there is no explicit threshold alert when extraction ratios collapse.
5. **[P2] `scrape_runs` history table.** Persist run-level health/throughput metrics to identify drift trends over time.

---

## Addendum — 2026-04-23 (Phase B guardrails shipped)

Outreach automation now has persistent policy enforcement and auditability:

1. **Implemented:** DB-backed outreach policy in `app_settings` (enable switch, daily cap, send window + timezone, allowed statuses, suppression toggle).
2. **Implemented:** suppression list table + CRUD endpoints.
3. **Implemented:** outbound send log table with `sent|failed|blocked` status for auditability and cap enforcement.
4. **Implemented:** `send-outreach` now enforces policy, window, cap, status allowlist, suppression checks, and do-not-contact note checks.
5. **Remaining P1:** add UI for policy/suppression management so all controls are operable without API calls.
6. **Remaining P1:** add per-campaign caps and cooldown spacing (current cap is app-level daily).

---

## Addendum — 2026-04-23 (Settings UI handoff pass)

Status update to keep this audit accurate for future sessions:

1. **Resolved:** policy/suppression management is now available in the Settings UI (no API-only gap).
2. **Resolved:** SMTP/outreach env settings are editable in UI and persisted via `/settings`.
3. **Resolved:** send guardrails are now operable end-to-end without manual `.env` editing.
4. **Open P1:** add campaign-level segmentation (per-campaign caps, cooldown, sequence pacing).
5. **Open P1:** add inbound reply ingestion + intent triage (Phase 17 target).
6. **Open P2:** add UI test coverage for Settings dialog guardrail and suppression workflows.

---

## Addendum — 2026-04-23 (client lifecycle automation blueprint)

Strategic direction (documented in `docs/CLIENT_LIFECYCLE_AUTOMATION.md` and reflected in `GOALS.md`, `ARCHITECTURE.md`, `OUTREACH_AUTOMATION_ROADMAP.md`, `INTEGRATION.md`, `HANDOFF.md`, `.cursorrules`):

1. **[P1] Workflow backbone.** Introduce explicit workflow **state** + **job queue** semantics (idempotent jobs, retries, stuck visibility) before scaling autonomous follow-ups or build automation.
2. **[P1] Engagement model.** Unify outbound sends, inbound MIME, classifications, and future call transcripts under one **thread/event** schema to avoid parallel incompatible logs.
3. **[P1] Confidence-gated automation.** Inbound triage (Phase 17) must ship with **confidence thresholds** and a **manual review queue**, not raw label-only output.
4. **[P2] Build pipeline.** Scoped generation → automated verification → preview deploy → approval/payment → promotion; tracked as first-class workflow stages.
5. **[P2] Observability layer.** Dashboards for sends/day, block reasons, time-in-stage, build pass rate, and human override rate on AI decisions.
6. **[P2] Commercial checkpoint.** Wire minimal payment/terms gate before unattended production release (exact provider TBD).

---

## Executive Summary

The codebase is well-scaffolded and every phase in `MILESTONES.md` is cleanly implemented. The pipeline works end-to-end, tests pass, and the UI is polished. However, three structural weaknesses directly limit lead value:

1. **Scraping is brittle to Google's UI churn and bot detection.** Selectors are good, but detection surface is wide open (headless fingerprint, fixed UA, no stealth, no CAPTCHA handling, no selector-health telemetry). When Maps changes class names or blocks us, the pipeline will silently produce empty or partial leads with no alert.
2. **Lead scoring ignores monetary signals.** A 500-review / 4.9-star HVAC company with no website is infinitely more valuable than a 3-review restaurant with no website — but both get `lead_score = 10`. There is no weight for review count, rating, category value, or contact reachability.
3. **The app captures the bare minimum per lead.** No email, no hours, no owner name, no service area, no tech stack, no Google categories, no social profiles, no contact-page crawl. Each lead is worth less than it could be, and outreach requires the user to re-gather info manually — defeating the "time = money" goal.

The rest of the report is a numbered list. Each item is actionable. The final section is a prioritized roadmap.

---

## 1. Scraping Hardening & Future-Proofing

### 1.1 Bot-detection & fingerprint

1. **[P0] Hardcoded Chrome 124 UA** (`src/scraper/maps.py:33-37`, `src/scraper/evaluator.py:56-64`). Google will increasingly distrust stale UAs. Rotate across a small pool of current UAs (Chrome 131+, Safari, Firefox) or pull from `fake-useragent` and pin via env.
2. **[P0] No Playwright stealth hardening.** No `navigator.webdriver` spoof, no canvas/WebGL fingerprint patch, no `Intl`/`languages` override. `playwright.chromium.launch(headless=True)` at `src/pipeline.py:100` is the easiest fingerprint Google has. Recommend `playwright-stealth` or manual `add_init_script` to hide `webdriver`, override `navigator.plugins`, `chrome.runtime`, and `Notification.permission`.
3. **[P0] `headless=True` always.** No env toggle. Cannot run headed for debugging, and new headless mode (`headless="new"` / `--headless=new`) is less detected than the default old headless. Expose via `settings.headless` and default to new-headless.
4. **[P1] No `BrowserContext` with locale / timezone / viewport.** Defaults make us an obvious bot. Set `locale="en-US"`, `timezone_id="America/Boise"`, realistic viewport (`1440x900`), `geolocation={"latitude":43.615, "longitude":-116.2023}`, and `permissions=["geolocation"]`. Maps uses geolocation hints and will serve better data for local queries.
5. **[P1] No persistent storage state.** Every run re-does the consent dance, and Google sees a "fresh visitor" over and over. Save `context.storage_state()` to disk and reuse across runs.
6. **[P2] Proxy / IP rotation hook.** Not needed now, but the single residential IP is a forever-liability. Add an unused but wired-through `settings.proxy_url` so we can plug in a proxy the day we need one (Webshare, IPRoyal, etc.).

### 1.2 Selector resilience

7. **[P0] No selector-health telemetry.** If Google changes `.hfpxzc` or `.Io6YTe` to something new, `_collect_card_hrefs` will return `[]` with no warning louder than `logger.warning`. Add a per-run summary log at `INFO`: `[category] hrefs=0 names=0 → probable selector drift`. Even better: surface a `selector_health` dict in `GET /scrape/status` and the StatsBar.
8. **[P1] Empty-result signal not differentiated.** `scrape_category` returning `[]` could mean "no businesses" or "Google changed the DOM". Track `hrefs_found` vs `results_extracted` vs `duplicates_skipped` and persist them on a `scrape_runs` table (see §4.1) so drift is visible over time.
9. **[P1] Place-detail consent handling.** `_handle_consent` runs only after the first search navigation (`_collect_card_hrefs`). If consent surfaces on a place detail page (EU IP, server-tagged session, etc.), `_extract_place_data` will silently fail. Call `_handle_consent(page)` at the top of `_extract_place_data` too.
10. **[P1] `FEED_SELECTORS` / `CARD_SELECTOR` not versioned.** When Google breaks them, we'll patch in-place with no history. Introduce `src/scraper/selectors.py` with a dated dict so we can A/B selectors without losing the previous working set.
11. **[P2] No CAPTCHA / "sorry" page detector.** If Google redirects us to `google.com/sorry/...`, we just time-out and score 0 leads that run. Detect the URL prefix / "unusual traffic" body text and abort the run with a loud error (and a one-time notification via log at `CRITICAL`).
12. **[P2] `extract_place_id_from_url`** only handles `ChIJ…` and `0x…:0x…` — misses the newer `GhIJ…` variant Google has been rolling out. Add a third regex and fall back to a `data-pid` attribute on the place-detail container.

### 1.3 Scroll & timing robustness

13. **[P1] `max_stale = 4`** with 2–4 s scroll pause (`src/scraper/maps.py:265`). On slow connections the last two scrolls can both be "stale" simply because the feed is still rendering. Bump `max_stale` to `6`, or require stale-count after a forced `page.evaluate('document.body.offsetHeight')` paint wait.
14. **[P1] No scroll-to-bottom verification.** Current loop can stop at 12 cards when the feed has 60. Add a final pass: after `stale_scrolls >= max_stale`, do one hard scroll to `scrollHeight` and re-collect before returning.
15. **[P2] `MAX_RESULTS=60` is a constant.** Move to `settings.scrape_max_results`. Different categories may want different caps (e.g. "restaurants" has 500+ results, "chiropractor" might have 40 total — we'd benefit from `max_results_per_category: dict[str, int]` override).
16. **[P2] `LOCATION = "Boise Idaho"` hardcoded at module scope** (`src/scraper/maps.py:29`). Should come from `settings.scrape_location` so we can add Meridian, Nampa, Caldwell, Eagle without a code change. Hot-swapping location is the cheapest way to 3× our lead volume.

### 1.4 HTTP evaluator hardening

17. **[P0] `is_social_url` misses critical directory/booking domains.** Missing: `vagaro.com`, `squareup.com`, `square.site`, `wix.com`, `weebly.com`, `godaddysites.com`, `sites.google.com`, `linktr.ee`, `mapquest.com`, `bbb.org`, `superpages.com`, `yellowpages.com`, `manta.com`, `opentable.com`, `doordash.com`, `grubhub.com`, `ubereats.com`, `groupon.com`, `booksy.com`, `styleseat.com`, `schedulicity.com`, `setmore.com`, `calendly.com`, `pinterest.com`, `tiktok.com`, `youtube.com`, `etsy.com`, `shop.app`. Any of these should score a 9, not fall through to the AI path (where we waste a token call and get a high AI score that caps their lead score at 1).
18. **[P1] HTML snippet = raw first 3000 chars** (`src/scraper/evaluator.py:161`). This frequently includes only `<head>` tags, meta, and inline `<style>`, giving the AI almost nothing actionable. Strip `<script>` / `<style>` / comments, collapse whitespace, then take the first 3000 chars of visible-ish content.
19. **[P1] No timeout differentiation in retries.** `tenacity` retries `TimeoutException | ConnectError` with the same 10 s timeout both times. First attempt should be 5 s, retry at 15 s — a slow site is still a signal, not a hard 4-fail.
20. **[P2] No TLS error distinction.** Expired cert vs self-signed vs no HTTPS all collapse to "score 8". Expired cert alone is a great pitch angle ("your padlock is red and customers flee") and should be captured separately (`ssl_expired: bool`).
21. **[P2] Final-URL redirect introspection.** We use `response.url` for `has_ssl`, good — but we don't capture the redirect chain. A business whose google-listed URL is `http://…` but redirects to HTTPS is a better lead than one on flat HTTPS (they haven't bothered to update Maps). Store `redirected: bool` and `redirect_count`.

### 1.5 AI scoring resilience

22. **[P1] Model names hardcoded** (`gemini-1.5-flash`, `llama3-8b-8192`). Google and Groq deprecate models every ~6 months. Move to `settings.gemini_model` / `settings.groq_model` with current defaults (`gemini-2.0-flash` is now GA and cheaper; `llama-3.3-70b-versatile` is Groq's live equivalent).
23. **[P1] No JSON schema enforcement.** `parse_ai_response` strips markdown fences because the model sometimes wraps JSON. `google-genai` supports `response_mime_type="application/json"` + `response_schema`. Enforce it and we eliminate an entire failure mode.
24. **[P1] Rate-limit detection is substring-matched** (`"429" in err`). Fragile. Catch the typed exception (`google.api_core.exceptions.ResourceExhausted` or `google.genai.errors.APIError` with `.status_code`). Groq also 429s — same pattern applies (`groq.RateLimitError`).
25. **[P2] No retry with backoff before fallback.** Gemini has a per-minute quota. Current code flips to Groq on the first 429 for the rest of the session. Wait 60 s and retry once (as the spec in `INTEGRATION.md:82` suggests but the code doesn't implement); only then fall back. Saves Groq quota for real failures.
26. **[P2] No fallback beyond Groq.** When both fail we just write `None`. A third tier could be a tiny on-device heuristic (`no-viewport + old copyright + http-only → score 5`) so we never return null from AI.

### 1.6 Integration-test gap

27. **[P1] No real-DOM snapshot test for Maps scraper.** `tests/test_maps_helpers.py` only covers pure helpers. Save a recent `page.content()` HTML snapshot per category as a fixture; run `_collect_card_hrefs`-style parsing against it in CI so selector drift fails a test before it reaches production.
28. **[P2] No evaluator HTTP test with httpx mock.** `respx` makes this a one-liner. We'd catch regressions on the social-URL matcher and status-code branches.

---

## 2. Lead Scoring — Monetary Weighting

The current rubric (`src/scorer/lead.py`, `INTEGRATION.md:36-50`) is purely about website quality. It ignores whether the business is worth pursuing.

### 2.1 Missing monetary signals

29. **[P0] Review count is ignored.** A plumber with 400 reviews is a proven business that can spend $3k on a site; one with 2 reviews may not exist in a year. **Recommend:** add a `review_weight` multiplier — businesses with `review_count < 10` cap at `lead_score = 5`, `>= 100` get a +1 boost, `>= 500` get +2. Or: a separate `opportunity_score` field.
30. **[P0] Rating is ignored.** 4.5+ stars = beloved business, flush with customers, ideal target. <3.5 stars = struggling, less likely to pay. Add a rating floor (ignore `rating < 3.0` for top-tier) and boost (`rating >= 4.7` → +1).
31. **[P0] Category value is ignored.** Restaurants pay $500-1500 for a site. Plumbers, HVAC, dentists, chiropractors routinely pay $3k-10k. Introduce `CATEGORY_VALUE_MULTIPLIER` in `src/config/categories.py` — e.g. `{"dentist": 1.5, "plumbers": 1.4, "HVAC": 1.4, "chiropractor": 1.4, "restaurants": 0.9, ...}`. Surface it as the `expected_payout_tier: "premium"|"mid"|"low"` field in the UI.
32. **[P1] Contact reachability not scored.** No phone = hard lead. Phone + email = easy lead. Currently phone presence is extracted but not scored. Add `has_phone` / `has_email` to the rubric.
33. **[P1] Copyright year underused.** We extract it but never use it. A `copyright_year < current_year - 3` is a MASSIVE redesign signal — should bump `lead_score` +1 independent of AI score.
34. **[P1] `ai_score ≥ 7 → lead_score = 1`** (`src/scorer/lead.py:57`) is an over-punishment. A "decent" site with 5 reviews is still a valid lead for upsell (SEO, maintenance plan, new landing pages). Recommend `lead_score = 2` minimum floor here.
35. **[P2] 1–10 integer scale is too coarse.** With binary decisions on SSL / mobile / AI-bands, every "no website" lead is indistinguishably 10. Consider a composite `0.0–100.0` `opportunity_score` as a new column, keep `lead_score` as the coarse display bucket.

### 2.2 Silent failures in scorer

36. **[P1] `calculate_lead_score` returns `3` on any exception and doesn't log** (`src/scorer/lead.py:62`). If our rubric starts throwing (e.g. because a new field is `None`), we'd never know — and all leads would quietly land in the middle bucket. Log `exc_info=True` before returning the fallback.

---

## 3. Data Capture — "As Much Information As Possible"

Every missing field is a piece of info the user will have to look up manually before a first outreach. Each minute saved per lead × hundreds of leads = real payout. The goal should be: **every useful fact visible on the Google Maps listing and the business website should land in `leads.db`**.

### 3.1 Google Maps fields we currently skip

37. **[P0] Hours of operation.** Shown plainly on the Maps side panel, extractable from `div[aria-label*="Hours"]` / `table.eK4R0e` or the `hours` attribute. Knowing "open Sundays" or "closed Mon-Wed" is huge context.
38. **[P0] Google categories (primary + secondary).** Google shows them right under the business name. Much more accurate than our scraped search category. Selector: `button[jsaction*="category"]`.
39. **[P0] "Claimed vs unclaimed" status.** Unclaimed listings = owner hasn't touched their web presence in years = perfect lead. Detectable via the "Claim this business" CTA.
40. **[P0] Photo count.** Businesses with <5 user photos are usually underserved. Selector: `button[aria-label*="photo"]` text.
41. **[P1] Business description (About tab).** Often contains owner's name, years in business, specialties — gold for personalized outreach.
42. **[P1] Service area / "Provides: …" chips.** E.g. plumbers often list "Water heater repair, Drain cleaning" — lets us personalize the pitch.
43. **[P1] Price range (`$`, `$$`, `$$$`).** Restaurant-specific but a clear monetary tier signal.
44. **[P1] Booking / menu / order link.** If they use Vagaro / OpenTable / Toast, we know their budget and their current SaaS bill.
45. **[P2] Popular times.** Heatmap data indicates how busy they actually are. Hard to parse but possible.
46. **[P2] "Owned by" / minority-owned / veteran-owned attributes.** Good outreach hooks; trivially extractable from the chips.

### 3.2 Website fields we currently skip

47. **[P0] Email extraction.** Crawl `mailto:` links from the homepage AND `/contact`, `/about` pages. Already-extracted phone is table stakes; an email is what lets us actually send outreach. This is the single highest-ROI capture add.
48. **[P0] Contact-page crawl.** We only fetch the homepage. One additional fetch of `/contact` or the page linked from the footer "Contact" link gets us email, hours, owner name, second phone, sometimes even staff names.
49. **[P1] Social profile links on their site.** Facebook, Instagram, LinkedIn URLs extracted from `<a href>` tags. Lets us verify the owner across platforms. Selector: `a[href*="facebook.com"]`, etc.
50. **[P1] Tech-stack fingerprint.** `window.Wix`, `window.squarespace`, `wp-content/`, `cdn.shopify.com`, `static.parastorage.com`, `godaddy`-builder signatures. Knowing they're on Wix lets the pitch write itself. A tiny regex dict in `evaluator.py` solves this for 90% of cases.
51. **[P1] Approximate page-load weight.** Total response bytes + script count. A 5 MB homepage is a layup for a rebuild pitch.
52. **[P2] Owner first name from About page.** Regex like `r"Owner:?\s+(\w+)"` or `r"I['']?m (\w+)"` — imperfect but massively personalizes outreach.
53. **[P2] Blog freshness.** Link to `/blog` or `/news` and extract the latest post date — "last blog post: Aug 2019" is a great opener.
54. **[P2] Page Speed Insights score (optional).** Free API, rate-limited. Could run on a cron on only the top-20 scored leads.

### 3.3 Schema implications

55. **[P1] DB schema needs additive columns.** Since `Base.metadata.create_all()` never adds columns to an existing SQLite, either (a) introduce Alembic now, or (b) add a startup bootstrap that runs `ALTER TABLE leads ADD COLUMN … IF NOT EXISTS` for each new optional field. See also §4.1.

---

## 4. Minimal User Interaction (time = money)

The user's hands should touch the keyboard only to: trigger scrape, review top leads, copy/email, archive. Anything more is friction.

### 4.1 Dashboard friction

56. **[P0] No "Top Today" / priority queue view.** User currently re-configures filters every session. Add a default pinned view: `lead_score >= 7 AND status = 'new' AND created_at > now() - 7d`, sorted by a new `opportunity_score`. This should be the landing page — zero clicks to the list that matters.
57. **[P0] No CSV / JSON export.** Critical for moving leads into any CRM/spreadsheet/outreach tool. `GET /leads/export?format=csv` + an "Export N leads" button on the filter bar. Selection-based export (see §4.3) is ideal.
58. **[P0] No email / phone copy-to-clipboard button.** `mailto:` / `tel:` links exist, but we also need a one-click "Copy" next to each so the user can paste into their outreach tool without losing flow.
59. **[P1] No bulk actions.** Can't multi-select rows to archive, mark interested, export. A checkbox column + a floating action bar would save dozens of clicks per session.
60. **[P1] No scrape progress detail.** `GET /scrape/status` only reports `running: bool`. Add `current_category: str`, `categories_done: int`, `categories_total: int`, `businesses_processed: int`. Wire into `StatsBar` as a progress bar. User no longer has to wonder "is this still working?".
61. **[P1] No scrape completion notification.** Even a `document.title = "✓ Scrape complete"` flash + a toast would remove the need to watch the bar.
62. **[P1] No keyboard shortcuts.** `j`/`k` to move row, `Enter` to open sheet, `a` to archive, `i` to mark interested, `/` to focus search, `n` to start scrape. Massive UX multiplier for power users and very cheap to add with one `useHotkeys` hook.
63. **[P2] No saved filter presets / URL-backed filter state.** Filters live in `useFilters` but aren't in the URL. Bookmark-ability = zero. Push filters into the query string.
64. **[P2] No "last categories used" memory in `ScrapeModal`** (`frontend/src/components/ScrapeModal.tsx:22`). `useState<string[]>([])` on every open. Persist the last selection in `localStorage`.
65. **[P2] Selected lead ID not persisted.** Refreshing the page loses the open sheet. Push `?lead=123` into the URL.
66. **[P2] No undo for archive / delete.** One errant click loses a lead. A 5-second "Undo" toast after mutating status is a tiny mutation wrapper away.
67. **[P2] No snooze / follow-up.** A `follow_up_at: datetime` column + a filter "Due for follow-up this week" would let the user run outreach without a separate reminder tool.
68. **[P2] No pinned / starred leads.** Quick "my shortlist" view.

### 4.2 AI-drafted outreach (the biggest time saver)

69. **[P0] No AI-generated outreach template per lead.** We already have Gemini and Groq keys wired up. One additional call per lead, on-demand from the detail sheet ("Draft email"), returns a personalized first-message draft using `{name, category, ai_issues, owner_name?, city}`. This is the difference between "great tool" and "writes itself." Generate lazily, cache in `leads.outreach_draft` column.
70. **[P1] No AI-suggested pitch angle.** `ai_issues` lists problems; extend the prompt to also output `pitch_angle: str` (e.g. "Lead with mobile responsiveness — their site breaks on iOS Safari"). Two extra lines of prompt, surfaced in the detail sheet.

### 4.3 Rescraping stale leads

71. **[P1] No "force rescrape" per lead.** Once a lead is in the DB, its website evaluation is frozen. A business may have redesigned / closed / moved. Add `POST /leads/{id}/rescan` to re-run just the evaluator + AI scorer.
72. **[P1] No stale-lead refresh policy.** Leads older than 90 days with `status IN ('new', 'reviewed')` should auto-re-evaluate on the nightly run (not re-scrape, just re-check their website). Prevents the list from silently rotting.

---

## 5. Pipeline / Infra Future-Proofing

73. **[P0] No Alembic / migration tool.** `Base.metadata.create_all()` in `main.py:43` does not add columns to an existing table. Every schema change (and we have many listed above) will require either manual SQL or deleting `leads.db`. Wire Alembic in now before the schema diverges.
74. **[P1] Global module state.** `_scrape_state`, `_scrape_lock`, `_use_groq_fallback`, `_gemini_client`, `_groq_client` are module-level. Makes clean multi-run testing hard (partly mitigated by `reset_session()`). For a local single-process app this is acceptable, but wrap into a `ScrapeRunner` class when we add concurrent workers.
75. **[P1] `_scrape_state` shallow-copied** (`src/pipeline.py:43` — `dict(_scrape_state)`). The nested `categories` list is a shared reference; API consumers could theoretically mutate it. Use `copy.deepcopy`.
76. **[P1] Mixed timezone handling.** `datetime.now(UTC)` stored in `_scrape_state.started_at`, but `Lead.created_at` / `updated_at` use `func.now()` which on SQLite is naive local time. In `leads.py:26`, we then compute "today" from `date.today()` combined with `UTC` — which will be wrong for 6+ hours every day in MDT. Either store all timestamps as UTC tz-aware, or all as local naive. Current mix silently miscounts "new today".
77. **[P1] `Lead.ai_issues` defaults to `default=list`** but the column is `nullable=False`. If a bulk-inserted row skips it (e.g. Alembic migration), we'll crash. Set `default=list` is fine but add `server_default="[]"` too.
78. **[P1] No health check for AI keys / Playwright install at startup.** Everything deferred until first scrape. Better: a `POST /healthz/deep` (or one-shot `lifespan` probe) that pings Gemini with a single token and checks `playwright install chromium` has run. Fail fast = no surprise 2-hour-into-the-scrape blowup.
79. **[P2] No `scrape_runs` history table.** We log to a file but never persist summaries. Suggested schema: `id, started_at, finished_at, categories, businesses_scraped, new_leads, selector_failures, ai_calls, ai_429s, errors_json`. Powers a "past runs" view in the UI and is the canonical source for selector-drift detection (§1.2).
80. **[P2] No per-row DB session in pipeline.** One `SessionLocal()` wraps the entire scrape (`src/pipeline.py:102`). If SQLAlchemy loses connection mid-run (SQLite is forgiving but `aiosqlite` can still raise), the entire run has to rollback. A `async with SessionLocal()` inside `_process_business` makes each write atomic and independent.
81. **[P2] Bundle size 493 KB uncompressed** (per `MILESTONES.md:81`). Fine for local, but `date-fns`/`lucide-react`/`@radix-ui/*` can be code-split per route when we add more views.
82. **[P2] No React error boundary.** A crash inside `LeadDetailSheet` or the TanStack Table renderer white-screens the whole app.
83. **[P2] Log formatter is plain text.** For long-run debugging, JSON logs (via `python-json-logger`) make issues greppable by category and selector name.

---

## 6. Security & Compliance (sanity check)

84. **[P2] `.env` correctly in `.gitignore`.** Verified clean.
85. **[P2] No secrets committed in `.env.example`.** Verified clean.
86. **[P2] CORS restricted to `localhost:5173`.** Appropriate for local-only app.
87. **[P2] No auth on API.** Intentional — local-only. Note it in the README so this never silently migrates to a networked host.

---

## 7. Prioritized Roadmap (recommended execution order)

Rough order, optimized for payout velocity. Group [A] is "within a week", [B] is "next", [C] is "when convenient".

### Group A — Revenue-critical (start now)

1. **Capture email + contact-page crawl** (#47, #48) — single biggest payout lift.
2. **AI-drafted outreach + pitch angle** (#69, #70) — saves 5-15 min per lead × hundreds of leads.
3. **Review-count + rating + category value in lead score** (#29, #30, #31) — currently all "no-website" leads look identical. This is the difference between pitching a $200 lead and a $5,000 lead.
4. **`is_social_url` domain list expansion** (#17) — cleanup that immediately lifts lead quality.
5. **Playwright stealth + modern UA rotation + new-headless toggle** (#1, #2, #3) — one coordinated pass, buys us 6+ months of scrape stability.
6. **Selector-health telemetry + CAPTCHA detector** (#7, #11) — so when Google breaks us, we know within one run.
7. **Alembic migrations** (#73) — unblocks every other schema-touching item.
8. **Hours + Google categories + claimed status + photo count** (#37, #38, #39, #40) — four easy wins, huge context boost in the detail sheet.
9. **Export CSV + bulk actions** (#57, #59) — user flow completion.
10. **Top-Today default view + keyboard shortcuts** (#56, #62) — minimal-interaction win.

### Group B — Hardening (next)

11. **JSON schema enforcement on Gemini call + typed rate-limit catching + model in env** (#22, #23, #24).
12. **Scrape progress detail + completion notification** (#60, #61).
13. **Force-rescan endpoint + stale-lead auto refresh** (#71, #72).
14. **Copyright-year bonus + contact-reachability in lead score** (#32, #33, #34).
15. **`scrape_runs` history table + per-row DB session** (#79, #80).
16. **Strip `<script>`/`<style>` from AI snippet + HTML tech-stack fingerprint** (#18, #50).
17. **Business description + service area + booking link capture** (#41, #42, #44).
18. **Persistent browser storage state + geolocation context** (#4, #5).
19. **Location + max-results moved to config** (#15, #16).

### Group C — Nice-to-have

20. URL-backed filter state, lead-ID in URL, saved presets, undo toast, snooze, pins (#63-#68).
21. Page-speed / blog-freshness / owner-name heuristics (#51-#53).
22. Proxy hook, integration snapshot tests, React error boundary, structured logging (#6, #27, #82, #83).

---

## 8. What's Already Great (don't regress these)

- **Decision-tree evaluator with consistent return shape** (`src/scraper/evaluator.py:193-250`). Beautiful — callers never need to branch on the path.
- **`calculate_lead_score` pure + never-raises contract**. Exactly right discipline; keep this when adding signals.
- **Session-level Groq fallback flag**. Correct tradeoff; add typed exception catching and it's perfect.
- **One Playwright `Browser` shared across categories with per-category pages**. Efficient.
- **Async end-to-end all the way through the DB layer**. Easy to scale later.
- **TanStack Query placeholderData for smooth table transitions** (`LeadTable.tsx:141`). Small detail, great feel.
- **`reset_session()` for test isolation**. Wouldn't have remembered to export this; good.
- **`JsonList` TypeDecorator with empty-fallback**. Survives malformed JSON gracefully.
- **Selector banks with ordered fallbacks**. Right pattern, just needs telemetry around it (see #7).

---

*End of audit. Next step, when ready: pick items from Group A and approve a patch PR.*
