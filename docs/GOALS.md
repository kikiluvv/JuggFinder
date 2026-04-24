# JuggFinder — Project Goals

## Mission
Find local Boise businesses with weak or missing web presence, rank them by sales opportunity, and **orchestrate** the path from discovery through outreach, inbound handling, optional voice qualification, scoped delivery, and handoff — with **human-overridable** automation at every stage.

## North star (long term)
**Near–fully automated freelance web delivery:** the system finds leads, wins conversations, parses client intent, produces a verifiable web product behind preview gates, and delivers after explicit approval — minimizing repetitive work while preserving **hard gates** for money, law, and production risk.

Canonical technical blueprint: [`docs/CLIENT_LIFECYCLE_AUTOMATION.md`](CLIENT_LIFECYCLE_AUTOMATION.md).

## Current Core Outcome (Implemented)
- Scrape Google Maps by Boise-focused category queries.
- Evaluate website quality with deterministic checks plus AI scoring.
- Rank leads with both `lead_score` (1-10) and `opportunity_score` (0-100).
- Surface leads in a local dashboard for review, notes, status, and outreach drafting.
- Gated automated email send with DB-backed guardrails and send audit logging.

## Next Strategic Outcome (Planned)
- **Inbound:** ingest replies, classify intent with confidence scores, route low-confidence to manual review.
- **Orchestration:** durable **state machine + job queue** for stage transitions (not only request-time endpoints).
- **Unified engagement:** one thread model across email and future channels (voice, SMS).
- **Build pipeline:** spec → generate repo → automated verification → preview URL → promote after approval (and payment where required).
- **Voice (future):** first-touch qualification with transcript storage and mandatory human handoff on uncertainty.

## Scope and Constraints
- Local-first: runs on your machine, not public SaaS (until you explicitly choose otherwise).
- Boise-first: search and targeting remain geographically anchored to Boise.
- Free-tier-first: prioritize free or near-zero-cost options until ROI justifies upgrades.
- Human-overridable: automation is **pausable**, **auditable**, and **reversible** at every step.
- Hard gates: contracts, payments, production DNS, and legal exposure remain **explicit** checkpoints — not silently automated away.

## Outreach & Lifecycle Automation Principles
- **Warm and useful, never spammy:** no manipulative wording, no deceptive claims, no pressure language.
- **Consent-aware behavior:** respect unsubscribe and do-not-contact markers immediately on **all** channels.
- **Rate limits by design:** daily send caps, spacing/cooldown rules, business-hours delivery windows.
- **Traceability:** every generated message, classification, build, and promotion is logged with rationale where AI is involved.
- **Escalation safety:** uncertain inbound classifications and ambiguous scope route to **manual review**.
- **Idempotent side effects:** retries must not double-send, double-charge, or double-deploy.

## Phased Rollout (product capabilities)
1. **Draft Assist:** AI drafts outreach; human sends (or reviews before send).
2. **Gated Auto-Send:** policy-backed SMTP send with caps, windows, suppressions (**implemented**).
3. **Inbound AI Triage:** classify replies; confidence thresholds + review queue.
4. **Conversation Orchestrator:** follow-up drafts, cooldowns, max-touch rules.
5. **AI Call Rep (future):** first-touch qualification; transcripts; handoff rules.
6. **Workflow backbone:** explicit lead/client **states**, **workflow runs**, and **job queue** semantics (see lifecycle doc).
7. **Build & verify:** structured scope, generated repo, CI gates, preview deployments.
8. **Deliver & commercialize:** approval events, payments/contracts on the promotion path, production handoff.

## Success Criteria
- Top leads are ranked accurately enough that manual triage time keeps dropping.
- Outbound messaging quality feels personal and consistent.
- Inbound replies are organized with minimal manual sorting; override rate on AI labels is measurable.
- Conversion pipeline is measurable: discovered → contacted → replied → scoped → paid → preview → approved → deployed.
- Build pipeline: **mean time to preview** and **verification pass rate** trend better over time.

## Target Business Categories
Configurable, with current defaults including:
- Restaurants and cafes
- Auto repair shops
- Hair salons and barbershops
- Landscaping and lawn care
- Cleaning services
- HVAC, plumbers, electricians
- General contractors
- Small dental/chiropractic practices
- Pet grooming and boarding
- Local retail stores
- Independent real estate agents
