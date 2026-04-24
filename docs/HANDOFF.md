# Handoff Snapshot

Last updated: 2026-04-23

## Strategic backbone (read first)
Long-term direction is documented in **`docs/CLIENT_LIFECYCLE_AUTOMATION.md`**: state machine + job queue, unified **engagement** model, build **verify → preview → approve → release**, **commercial gates**, and **observability / kill switches**. Outreach Phases A–I in `docs/OUTREACH_AUTOMATION_ROADMAP.md` align to that blueprint. New work should extend those patterns rather than adding one-off endpoints per feature.

## Current Product State
- Scraping, evaluation, AI scoring, lead scoring, and dashboard review flows are operational.
- Outreach Phase B is operational:
  - AI draft generation
  - SMTP send endpoint
  - DB-backed guardrail policy
  - suppression list
  - send audit logging
- Settings dialog now edits:
  - env-backed SMTP/app settings
  - DB-backed outreach guardrails
  - suppression entries

## Key APIs to Know
- Lead and outreach:
  - `POST /leads/{id}/draft-outreach`
  - `POST /leads/{id}/send-outreach`
- Guardrails:
  - `GET /settings/outreach-policy`
  - `PATCH /settings/outreach-policy`
  - `GET /settings/outreach-policy/usage-today`
- Suppressions:
  - `GET /settings/outreach-suppressions`
  - `POST /settings/outreach-suppressions`
  - `DELETE /settings/outreach-suppressions/{id}`

## Operational Notes
- SMTP dry run is intentionally a developer-only terminal procedure (not in UI).
- For Gmail app-password SMTP, use:
  - host: `smtp.gmail.com`
  - port: `587`
  - TLS: enabled
- `smtp.google.com` may resolve but can fail TCP connect in some environments.

## Recommended Next Session Focus (Phase 17)
1. Sketch **`Engagement` / `EngagementEvent`** (or equivalent) so email outbound (`outreach_send_logs`) and future inbound share one model — avoids a second triage-specific schema that must be merged later.
2. Implement inbound reply **ingestion** (IMAP or webhook) and **raw persistence** (MIME/storage path + metadata).
3. Add AI **intent classification** with **confidence score** (`interested`, `not_now`, `not_interested`, `wrong_contact`, `unsubscribe`).
4. Route **low-confidence** rows to a **manual review queue**; high-confidence drives suggested next actions only (still overrideable).
5. Wire minimal **UI**: inbound list, thread view, override labels, link to lead.

**After Phase 17 (backbone before heavy automation):**
- Introduce **`WorkflowRun` / `WorkflowEvent`** (or minimal state column + event log) before adding autonomous follow-up sends or build jobs — see lifecycle doc §3 and §10.
