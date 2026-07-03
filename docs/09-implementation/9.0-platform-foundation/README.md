# Sub-stage 9.0 — Platform Foundation

**Status:** `APPROVED` (2026-07-02)
**Depends on:** Stages 3–8
**Owner roles:** Senior Python Developer, Senior DevOps Engineer
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Not persona-facing itself — this sub-stage exists so 9.1+ (PR Analysis, first
persona-facing MVP capability) has an auth model, event backbone, and ingestion
adapter to build on. See `docs/09-implementation/README.md` for why foundation
comes first.

## Scope

**In scope:**
- Project skeleton (`pyproject.toml`, `src/sibyl/` package layout mirroring the
  Stage 3 bounded contexts, tooling config for Ruff/MyPy/Pytest).
- Identity/Access: `installation`/`installation_repository` tables, JWT
  create/decode, `require_scope` FastAPI dependency (RBAC enforcement per Stage 5).
- Ingestion: GitHub webhook receiver (`POST /webhooks/github`) with HMAC signature
  verification, Redis-backed dedup fast path, durable `webhook_delivery` record,
  transactional outbox write.
- Platform shared layer: settings, OpenTelemetry + structlog wiring, the
  transactional outbox pattern (generic mixin + repository), a Kafka
  producer/consumer client, and the outbox→Kafka relay.
- Alembic configured with independent migration branches for the `identity` and
  `ingestion` schemas (per Stage 4 ADR), both applied against a real Postgres.
- FastAPI app factory with `/healthz` and `/readyz` (the paths the Stage 7 Helm
  chart's probes already reference).

**Explicitly out of scope (this pass):**
- `test_intelligence`, `pr_analysis`, `root_cause_analysis` schemas' *tables* — the
  schemas exist (Stage 7 init script) but their domain tables land with their own
  sub-stages (9.1, 9.2, 9.9), not here.
- **Token issuance, for both human and machine callers — deferred as one
  standing gap, tracked here explicitly (addendum, 9.2).** Only JWT *validation*
  (`require_scope`) is built; nothing mints tokens yet. This covers two related
  but distinct needs, both deferred together since they're really one
  Identity/Access feature (an issuance/admin flow), not two: (a) GitHub OAuth
  login for human users (needs a real GitHub OAuth app), and (b)
  installation-scoped tokens for CI jobs calling `POST /ingest/test-results`
  (9.2) — as of 9.2, that endpoint *requires* an `installation_id` claim on the
  token (a real security fix, see 9.2's Changelog) but nothing issues such a
  claim yet, so the endpoint is only usable today via tests that mint tokens
  directly. Deferred because building a real issuance/admin flow is a
  self-contained feature deserving its own focused pass, not a few lines added
  opportunistically to whichever sub-stage happens to need a token next — but
  flagged here so it isn't quietly forgotten as "someone else's problem."
- Structured, per-event-type Kafka payloads. Ingestion forwards the raw GitHub
  webhook JSON as the outbox/Kafka payload for now — `EventEnvelope[PayloadT]`
  (already defined, currently 0% exercised) is the pattern later sub-stages use
  once they define concrete payload schemas (e.g. `PrChangedPayload`). Forcing a
  typed payload now, before any consumer needs one, would be guessing its shape.
- The Kafka consumer side (`KafkaConsumerClient.consume_forever`) has no caller
  yet — 9.1 is the first real consumer.

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: `docs/05-api-design/openapi.yaml` (`/webhooks/github`)
- Data model: `docs/04-database/README.md` (`identity`, `ingestion` schemas; outbox
  pattern; Redis dedup/rate-limit catalog)
- Runtime flow: `docs/06-sequence-diagrams/README.md` §1 (PR Analysis primary flow,
  ingestion portion), §7 (ingestion failure/retry)

## Design notes specific to this sub-stage

- **Alembic branch mechanics**: `version_locations` in `alembic.ini` plus
  `-x schema=<name>` passed to `alembic revision --autogenerate` and consumed by an
  `include_object` filter in `alembic/env.py` — this is what makes each schema's
  migration history independent while sharing one `alembic_version` tracking table.
  Verified live: `alembic upgrade heads` applied both branches against a real
  Postgres container; `\dt identity.*` / `\dt ingestion.*` confirm exactly the
  expected tables per schema.
- **Installation resolution is create-on-first-sight**: a `pull_request`/`check_suite`
  webhook for an unseen `github_installation_id` creates a minimal `Installation`
  row rather than erroring — consistent with the Stage 6 "tolerate out-of-order
  arrival" principle applied to the `installation` webhook event specifically.
- **Cross-stage fix caught during this sub-stage**: `docs/09-implementation/README.md`'s
  original 9.9 (Root Cause Analysis) dependency table is unaffected, but the CI
  pipeline (Stage 7) had `services:` blocks for Postgres/Redis that duplicated what
  Stage 8 already named `testcontainers` for — removed the `services:` blocks
  since `testcontainers` alone (already proven to work in this sub-stage's own test
  suite) is sufficient on `ubuntu-latest` runners.

## Test plan

Per `docs/08-testing-strategy/README.md`, executed for real (not just planned):

- **Unit** (no DB/network): HMAC signature verification, JWT create/decode
  round-trip and failure modes, `require_scope` dependency logic, event-type→topic
  mapping.
- **Integration** (real Postgres + Redis + Kafka via `testcontainers`, not mocks):
  webhook dedup, outbox add/fetch/mark-published, the outbox→Kafka relay
  end-to-end (verified a real consumer receives the published message), installation
  repository idempotency.
- **Full flow**: `POST /webhooks/github` exercised through the actual FastAPI app
  (`httpx.AsyncClient` + `ASGITransport`, real lifespan) — happy path, invalid
  signature, duplicate delivery, malformed payload.

Result: 27 tests, all passing; 90% coverage overall. `ruff check .` and
`mypy src tests` (strict) both clean.

## Observability

- Traces: `configure_observability` wires an OTLP span exporter — no explicit spans
  added yet inside handlers (structured log events serve that role for now); span
  instrumentation is added alongside 9.1's actual analysis logic where "start of a
  meaningful unit of work" is easier to define correctly.
- Logs: `structlog` JSON logs at webhook accept/duplicate (`webhook.accepted`,
  `webhook.duplicate`) per the Stage 6 diagram's log touch points.
- Metrics: OTLP metric exporter wired; no counters emitted yet in this sub-stage
  (the Stage 6 diagrams' metric names like `ingestion.webhook.accepted_total` are
  the contract 9.1 wires against once a real consumer exists to observe alongside).

## Security considerations

- Webhook authenticity: HMAC-SHA256 verified via `hmac.compare_digest` (constant-time,
  not `==`) against the GitHub App's webhook secret — tested against both a
  tampered body and a missing header.
- JWT: HS256, signing key from `Settings` (env-sourced, never hardcoded beyond the
  local-dev default placeholder, which is explicitly named `local-dev-...-not-for-production`
  so it can't be mistaken for a real key).
- No secret is logged: the webhook secret and JWT signing key are read from
  `Settings` and never included in the `structlog` log events.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code (verified by inspection).
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 27 tests passing (unit + integration against real Postgres/Redis/Kafka),
      90% overall coverage, all identity/ingestion adapters at 100%.
- [x] Both Alembic branches (`identity`, `ingestion`) generated and applied against
      a real Postgres, verified via `\dt`.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian, explaining what/why for
      every file.
- [x] `PROGRESS.md` updated.
- [x] No secret committed (`.env` gitignored; `Settings` defaults are placeholders).

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: project skeleton, identity + ingestion contexts, event backbone (outbox + relay + Kafka client), Alembic branches, FastAPI app, full test suite. |
