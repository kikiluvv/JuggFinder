# Client Lifecycle Automation — Target Architecture

This document is the **north-star blueprint** for evolving JuggFinder from “lead discovery + outreach” into an **orchestrated client lifecycle**: discovery → outreach → reply triage → (optional) voice qualification → scoped build → verified preview → approved delivery — with **explicit gates**, **auditability**, and **near-zero-touch operation** where it is safe.

It complements `GOALS.md`, `ARCHITECTURE.md`, and `OUTREACH_AUTOMATION_ROADMAP.md`. Implementation is intentionally **phased**; nothing here implies shipping all layers at once.

---

## 1. Guiding principles

1. **Stages, not scripts.** Long-running work is modeled as **states** and **transitions**, not a single linear pipeline function.
2. **Durable workflows.** Side effects (email, deploy, calls) run as **jobs** with retries, idempotency keys, and visible failure reasons.
3. **Shrink the human loop, do not delete judgment.** Automate drafting, scheduling, classification, and QA; **reserve hard gates** for money, law, reputation, and production infra.
4. **One conversation truth.** Email, future SMS, and voice all append to a single **engagement / thread** model per lead (or per client account).
5. **Promote builds that pass gates.** Generation is cheap; **verification + preview + approval** is the product.

---

## 2. Target state machine (conceptual)

States are illustrative; exact enums will evolve with the schema.

| Stage | Meaning |
|--------|---------|
| `discovered` | In DB from Maps; may not be qualified for contact |
| `qualified` | Meets policy + score thresholds for outreach |
| `contacted` | Outbound first touch sent (or queued) |
| `replied` | Inbound signal received (email parse, webhook, etc.) |
| `scoped` | Structured scope captured (template + AI extraction + optional client form) |
| `building` | Repo/generator running; no production DNS change |
| `preview_sent` | Ephemeral preview URL available to client |
| `approved` | Client explicitly approved scope and/or preview (logged) |
| `deployed` | Production or handoff deploy completed |
| `handed_off` / `archived` | Closed loop; won/lost/nurture |

**Transitions** are only taken when **policy + confidence + commercial** checks pass (see §5).

---

## 3. Job queue and orchestration

**Today:** FastAPI + `BackgroundTask` + APScheduler for scrape; outreach is request-driven with DB policy.

**Target:** A small **orchestrator** layer (still can live inside FastAPI initially) that:

- Enqueues **workflow runs** (`WorkflowRun`) keyed by lead/client + stage.
- Executes **idempotent jobs** (`send_first_touch`, `parse_inbound`, `classify_reply`, `generate_repo`, `run_ci_checks`, `deploy_preview`, `promote_production`).
- Records **append-only events** (`WorkflowEvent`) for every transition and side effect.
- Supports **timeouts** and **dead-letter** behavior (stuck jobs surface in UI).

**Later scale option:** migrate the same semantics to Celery/RQ/Temporal if you need distributed workers — the **state machine contract** stays stable.

---

## 4. Unified engagement model

Replace duplicated “email logic here, call logic there” with:

- **`Engagement`** (or `Thread`): links `lead_id`, channel (`email` \| `voice` \| future channels), external ids (Message-Id, call SID).
- **`EngagementEvent`**: append-only rows for outbound send, inbound raw MIME, transcript chunk, classification result, human override.

**Cross-cutting rules:**

- **Suppression and consent** are checked at **every** outbound attempt on **every** channel.
- **Confidence thresholds** (from triage or call summarization): above threshold → suggested or auto next step; below → **manual review queue**.

---

## 5. Human-in-the-loop gates

### Hard gates (keep long-term)

- Contract / **scope acceptance** with revision limits.
- **Payment** or deposit captured before expensive build or production deploy.
- **Production DNS / domain** changes and any **legal** commitments.
- First deployment to a **live** hostname the client already uses for revenue.

### Soft gates (automate aggressively)

- Draft generation, scheduling, labeling, internal previews.
- CI-style checks (lint, tests, Lighthouse budgets, broken links, basic a11y smoke).
- Ephemeral **preview deployments** (no client DNS until approval).

---

## 6. Build → verify → preview → release

Structured pipeline for “generate a webapp and deliver”:

1. **Spec layer** — structured JSON (or DB columns): pages, brand tokens, integrations, content sources. Populated from triage + optional **client form link** (“pick template A/B/C”).
2. **Generator** — produces a **repo artifact** from templates + AI fill-in; never edits prod blindly.
3. **Verification** — automated: unit/integration where applicable, static analysis, performance/accessibility budgets, link scan.
4. **Preview** — ephemeral URL (e.g. Vercel/Netlify/Cloudflare preview); share with client.
5. **Release** — promotion only after **explicit approval event** (button + timestamp in DB) and **payment state** if required.

Rollback and “promote previous preview” remain first-class ideas.

---

## 7. Commercial and legal envelope

Fully automated “client → deliverable” implies:

- **Terms + IP assignment** (even if lightweight).
- **Invoicing / card capture** (e.g. Stripe Checkout) tied to state transitions (`scoped` → `paid` → `building`).
- **Audit trail** for what the client saw and approved.

Without this layer, automation optimizes for **shipping**, not **getting paid** or **limiting liability**.

---

## 8. Observability and kill switches

- **Dashboards:** sends/day, block reasons, triage precision vs human overrides, build failure rate, time-in-stage.
- **Global pause:** one flag stops outbound, calls, and promotions without corrupting data.
- **Per-lead pause** and **domain/email blocklist** (extends today’s suppression concept).

---

## 9. Voice agent (future channel)

Same engagement model as email:

- First-touch **qualification only**; no closing or legal/financial promises.
- **Transcript + summary + action items** stored as `EngagementEvent` rows.
- **Handoff** when ambiguity, objection, pricing negotiation, or legal topic detected.

---

## 10. Sequencing recommendation (implementation order)

1. **Workflow backbone** — `WorkflowRun` / `WorkflowEvent`, job idempotency, UI for queue and failures.
2. **Engagement + inbound** — ingest email (IMAP/webhook), raw storage, classification with confidence + review queue (Phase 17).
3. **Conversation orchestration** — follow-up drafts, cooldown rules, max-touch limits (Phase D in outreach roadmap).
4. **Scoped generation + CI + preview URLs** — treat as one deliverable milestone.
5. **Payments/contracts on the critical path** — before unattended production release.
6. **Voice** — after email + triage + build loop are stable (failures amplified on phone).

---

## 11. Relation to current codebase

| Area | Today | Moves toward |
|------|--------|----------------|
| Leads | SQLite `Lead`, dashboard | Same + optional `qualified` automation rules |
| Outreach | Draft + gated send + logs | Events on `Engagement` / `EngagementEvent` |
| Triage | Planned | Classification jobs + review queue |
| Build | N/A | Generator jobs + verify + preview |
| Ops | Logs, settings UI | Metrics + global pause + dashboards |

This document should be updated whenever major architectural decisions are made (e.g. choosing Temporal vs in-process queue).
