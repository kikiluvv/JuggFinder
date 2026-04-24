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

## Milestone 17.2 — Inbound capture MVP ✅

| Item | Description |
|------|-------------|
| **API** | `POST /leads/{id}/inbound` with `from_email`, `to_email`, `subject`, `body`, optional `message_id` — stores `inbound_received` on the engagement timeline (`record_inbound_received`). |
| **Dev dry-run** | With `DEV_PIPELINE_DRY_RUN_ENABLED=true`, `POST /dev/pipeline-dry-run` seeds/refreshes **TEST BUSINESS** (`place_id=dev:juggfinder-test-business`, email from env default `1kikiluvv@gmail.com`), optional real AI `draft`, **simulated** `outreach_sent` (timeline only, no SMTP / no `outreach_send_logs`), and simulated `inbound_received`. |
| **Tests** | `tests/test_phase17_2_inbound_and_dry_run.py` — inbound HTTP (mini ASGI app), `execute_dry_run`, mocked draft, `/dev` mini-app. |

**Exit:** Inbound POST + dry-run steps covered by tests; Activity UI shows `inbound_received` (label: “Inbound email”).

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
