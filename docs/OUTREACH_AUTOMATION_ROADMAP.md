# Outreach Automation Roadmap

This roadmap extends JuggFinder from lead discovery into outreach execution while keeping the system local-first, polite, and controllable.

**Parent blueprint:** end-to-end lifecycle (state machine, job queue, engagement model, build/deliver, commercial gates) lives in [`docs/CLIENT_LIFECYCLE_AUTOMATION.md`](CLIENT_LIFECYCLE_AUTOMATION.md). Phases A–E below focus on **communication**; Phases F–I describe **delivery and orchestration** that consume the same engagement and policy concepts.

## Objectives
- Reduce time from "new lead" to "first qualified conversation."
- Keep message quality human and context-aware.
- Automate only where confidence and compliance are acceptable.
- Preserve manual override at every stage.

## Rollout Plan

### Phase A — Draft + Human Send (current baseline)
- Keep `POST /leads/{id}/draft-outreach` as the primary generation path.
- Add draft quality guardrails (tone, length, banned claims).
- Track draft generation rate and edit distance (how much user rewrites).

### Phase B — Gated Auto-Send (implemented)
- Send endpoint: `POST /leads/{id}/send-outreach`.
- Guardrail policy is DB-backed (settings table), exposed via:
  - `GET /settings/outreach-policy`
  - `PATCH /settings/outreach-policy`
- Suppression list management:
  - `GET /settings/outreach-suppressions`
  - `POST /settings/outreach-suppressions`
  - `DELETE /settings/outreach-suppressions/{id}`
- Usage telemetry endpoint:
  - `GET /settings/outreach-policy/usage-today`
- Enforced controls:
  - global outreach enable/disable
  - daily send cap
  - send window start/end + timezone
  - suppression enforcement toggle
  - allowed lead statuses for send
- Outbound events are persisted in `outreach_send_logs` with statuses (`sent`, `failed`, `blocked`).
- Settings UI now supports editing SMTP/env fields, guardrail policy, and suppression list directly.

### Phase C — Inbound AI Processing
- Ingest replies and classify:
  - `interested`
  - `not_now`
  - `not_interested`
  - `wrong_contact`
  - `unsubscribe`
- Extract structured fields: preferred contact time, requested service, budget hints.
- Route low-confidence classifications to manual inbox review.
- Auto-create follow-up tasks for high-confidence `interested` and `not_now`.

### Phase D — Conversation Orchestration
- Generate reply drafts conditioned on inbound intent and prior thread.
- Add cooldown and max-follow-up rules to avoid over-messaging.
- Keep all sends overrideable with one-click pause/resume.

### Phase E — AI Call Representative (future)
- Scope: first-touch qualification only, not closing/sales negotiation.
- Must self-identify as an assistant and provide opt-out.
- Trigger human handoff on ambiguity, objections, pricing negotiation, or legal concerns.
- Store transcript + summary + action items in the lead record (prefer **`EngagementEvent`** rows aligned with email — see lifecycle doc).

### Phase F — Workflow backbone (future)
- Introduce explicit **workflow state** per lead/client (separate from dashboard `status` if needed, or mapped carefully).
- **Job queue** semantics: idempotent jobs, retries, timeouts, dead-letter / “stuck” visibility in UI.
- Central **orchestrator** (in-process first; optional migration to Celery/RQ/Temporal later without changing state contracts).

### Phase G — Unified engagement + inbound persistence (future)
- **`Engagement` / `Thread`** keyed by lead + channel; **`EngagementEvent`** append-only log (outbound, inbound raw, classification, human override).
- Email ingestion (IMAP polling or inbound webhook) stores **raw MIME** for audit and reprocessing.

### Phase H — Scoped generation + verification + preview (future)
- **Spec layer:** structured scope (pages, brand, integrations) from triage + optional client form.
- **Generator:** template-first repo or artifact; no blind production edits.
- **Verify job:** automated tests, link scan, performance/a11y budgets as configured.
- **Preview deploy:** ephemeral URL; client sees preview before any production DNS.

### Phase I — Commercial gate + release (future)
- **Approval event** logged (timestamp + actor) before `promote_production`.
- **Payment / deposit** (e.g. Stripe) as a hard gate before unattended production release or handoff.
- IP / terms checklist tied to `approved` → `deployed` transition.

## Technical Guardrails
- Never send when confidence checks fail.
- Never infer consent; require explicit allow-state for any autonomous campaign.
- Use deterministic policy checks before every outbound send (and before **call** or **deploy** actions when those channels exist).
- Keep all AI outputs editable by user before irreversible actions.
- **Idempotency:** job retries must not double-send, double-charge, or double-deploy; use idempotency keys and dedupe tables.

## Handoff Notes
- SMTP dry-run stays a developer/ops terminal procedure (not exposed in product UI).
- Gmail app-password setups should prefer `smtp.gmail.com` with TLS on port `587`.

## Compliance Baseline
- Honor unsubscribe immediately and permanently (unless manually reversed).
- Include clear identity and simple opt-out in outbound email templates.
- Respect sending-hour boundaries and conservative send volume.
- Maintain an auditable event trail for all outbound/inbound actions.

## Success Metrics
- Draft-to-send conversion rate.
- Positive reply rate from sent outreach.
- Time saved per 100 leads (manual baseline vs assisted flow).
- Inbound triage precision/recall against manually reviewed labels.
