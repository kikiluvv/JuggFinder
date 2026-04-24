# Phase 17 — Engagement Backbone & Inbound Triage

Phase 17 delivers the **client lifecycle pipeline** entry point: a unified **engagement thread** per lead (channel-scoped), **append-only events**, then **inbound capture** and **AI triage** with confidence + review queue.

Work is split into **milestones** so each merge is shippable.

---

## Milestone 17.1 — Engagement backbone ✅

| Item | Description |
|------|-------------|
| **Schema** | `engagements` (unique `lead_id` + `channel`), `engagement_events` (`event_type`, `payload` JSON, optional `outreach_send_log_id`, timestamps). |
| **Dual-write** | On `POST /leads/{id}/send-outreach`, after `outreach_send_logs` rows for **sent**, **blocked** (do-not-contact), or **failed** (SMTP error), append matching `EngagementEvent` types: `outreach_sent`, `outreach_blocked`, `outreach_failed`. |
| **Read API** | `GET /leads/{id}/engagement` — timeline ordered newest-first. |
| **UI** | Lead detail **Activity** strip listing recent events. |

**Exit:** Sending (or blocked/failed with a log row) shows on the Activity timeline without manual DB edits.

---

## Milestone 17.2 — Inbound capture MVP

| Item | Description |
|------|-------------|
| **API** | `POST /leads/{id}/inbound` with `from`, `to`, `subject`, `body`, optional `message_id` — stores `inbound_received` event (dev / manual paste friendly). |
| **UI** | Optional minimal form or dev-only; timeline shows inbound rows. |

**Exit:** A scripted or pasted inbound message appears on the same timeline as outbound.

---

## Milestone 17.3 — Triage v1

| Item | Description |
|------|-------------|
| **Classifier** | LLM labels + numeric confidence; config threshold in `app_settings`. |
| **Events** | `inbound_classified` (or equivalent) written after classification. |
| **Review queue** | `GET` listing low-confidence items + UI override → `human_override` event. |

**Exit:** Low-confidence inbound rows surface in a review list; overrides are auditable.

---

## Dependencies

- Phase 16 complete (outreach guardrails + `outreach_send_logs`).
- No new paid services required for 17.1–17.2.

## References

- `docs/CLIENT_LIFECYCLE_AUTOMATION.md`
- `docs/HANDOFF.md`
