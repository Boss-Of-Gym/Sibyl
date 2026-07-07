# Sub-stage 9.7 — Engineering Metrics

**Status:** `APPROVED` (2026-07-07)
**Depends on:** 9.0 (Platform Foundation), 9.1 (PR Analysis), 9.3 (Test Impact Analysis / Ingestion)
**Owner roles:** Senior Python Developer, Staff Backend Engineer
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

No Stage 1 persona evidences this directly — `docs/02-product-discovery/README.md`
places it in the "market/competitive only" evidence tier. Originally deferred:
Stage 9's roadmap description calls for "DORA-style metrics," and full DORA
(deployment frequency, lead time to production, change failure rate, MTTR) needs
deployment/incident event data this project has no ingestion source for.
Revisited per an explicit user request to close open deferrals rather than leave
them indefinite. Re-reading 9.7's own frozen dependency list (`9.0`, `9.1`, `9.3`
— no deployment infrastructure at all) shows a narrower, honestly-buildable
subset exists independent of that gap: aggregate PR-flow and CI-health signal
into read-time statistics over a time window. Full DORA remains deferred, now
for a documented reason instead of an open-ended "later."

## Scope

- In scope: `GET /repositories/{owner}/{repo}/engineering-metrics?windowDays=30`
  returning, computed at read time over the requested window: pull request
  count, median PR cycle time (merged PRs only, `merged_at - opened_at`), CI run
  count, CI success rate, and median CI run duration. Two local projections
  (`pr_lifecycle_projection`, `ci_run_projection`) built by consuming the raw
  `ingestion.pr-changed` and `ingestion.ci-run-completed` topics directly, as an
  independent Kafka consumer group.
- Explicitly out of scope (this pass):
  - Full DORA metrics (deployment frequency, lead time to production, change
    failure rate, MTTR) — genuinely blocked on a deployment/incident ingestion
    source that does not exist anywhere in this project. Not fabricated.
  - Pre-computed rolling rollups — statistics are computed at request time from
    stored per-PR/per-run rows, mirroring Test Intelligence's own
    `list_slow_tests`/`list_coverage_gaps` read-time ranking.
  - Any change to `pr_analysis` or `test_intelligence` — unnecessary, since the
    raw ingestion topics already carry every field this capability needs
    verbatim (see Design notes below).

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: `docs/05-api-design/openapi.yaml` — new
  `GET /repositories/{owner}/{repo}/engineering-metrics` endpoint, new
  `read:engineering-metrics` scope (new bounded context, so a new scope is
  correct, per the same reasoning 9.6/9.10 established).
- Data model: `docs/04-database/README.md` — new eighth schema
  `engineering_metrics` (`pr_lifecycle_projection`, `ci_run_projection`), no
  outbox table, no new Kafka topic.
- Runtime flow: `docs/06-sequence-diagrams/README.md` §13 — two independent
  projection-update triggers plus a read-time aggregation path, no LLM call,
  no publish.
- Bounded-context decision: `docs/03-architecture/adr/0002-bounded-context-map.md`
  addendum — new, eighth bounded context. Full ubiquitous-language evaluation
  (against `pr_analysis` and `test_intelligence` as join candidates) recorded
  there, not repeated here.

## Design notes specific to this capability

- **Why a new bounded context, not a join**: PR Analysis answers "how risky is
  this one PR's diff" (single-subject, structural); Engineering Metrics answers
  "how healthy is the PR flow in aggregate" (population-level, arithmetic).
  Test Intelligence's CI signals are keyed per-test; Engineering Metrics needs
  per-CI-run aggregates across a population of runs. Neither shares real
  domain language with this capability's question shape — see the ADR-0002
  addendum for the full evaluation.
- **No upstream change needed** — `ingestion/api.py`'s webhook handler
  publishes the entire raw GitHub webhook payload verbatim to
  `ingestion.pr-changed` (`payload=payload`), which already includes
  `pull_request.created_at`/`merged_at`/`closed_at`/`merged`. Similarly,
  `ingestion/test_results_api.py` publishes the full `POST /ingest/test-results`
  request body verbatim to `ingestion.ci-run-completed`. Any new consumer can
  read fields no *existing* consumer happened to model — no change to
  `pr_analysis`'s `PullRequest` ORM model or `test_intelligence`'s `TestRun`
  model was needed, despite neither modeling merge/close timestamps or
  run-level pass/fail counts today.
- **No outbox, no new topic** — the first bounded context with nothing to
  publish from day one. Nothing downstream needs to react to "PR/CI metrics
  were recomputed," so `worker.py`'s wiring for this context has no
  `run_relay_forever` task, only a consumer group.
- **Malformed-payload exception inherits `MalformedEventError` from the
  start** — `MalformedPrChangedPayload(MalformedEventError)`, consistent with
  the convention established during the launch-track Phase 1 Kafka retry/DLQ
  work and followed by 9.10. `CiRunCompletedReport.model_validate(payload)`
  failures are left unwrapped (raw `pydantic.ValidationError`), matching the
  established `test_intelligence.handle_ci_run_completed` precedent.
- **Upsert-by-natural-key, not append-only** — unlike
  `regression_prediction`/`pr_risk_assessment`/`root_cause_hypothesis`, both
  projections are upserted by `(repository, pr_number)` /
  `(repository, ci_run_id)` — this context stores current lifecycle/run state,
  not a history of predictions.

## Test plan

Per `docs/08-testing-strategy/README.md`: unit tests for `compute_median`/
`compute_ci_success_rate` (empty input, single value, odd/even counts,
all-passing vs. mixed failure rates); integration tests (real Postgres via
testcontainers) for the repository layer (create-then-update upsert semantics,
window-boundary exclusion), the service's two handlers (malformed-payload path,
a mixed merged/unmerged/still-open PR lifecycle scenario, CI test-status
counting), and the read API (200 with computed aggregates, 200-with-nulls for
an empty window, 403 without scope).

## Observability

`consumer.process` span and `consumer.processed_total` come for free from
`worker.make_dispatcher`, same as every other consumer group. No LLM call, so
none of the `llm.*` metrics apply to this capability — the first sub-stage
where that's true. No new per-capability named counters were added in this
pass, tracked as the same mechanical follow-up already logged for every other
capability's named counters in `docs/OPERATIONS_STRATEGY.md`.

## Security considerations

New `read:engineering-metrics` scope, correctly not reused from another
context (new bounded context). No new data sensitivity — repository names, PR
numbers, and timestamps already handled elsewhere in this system; no new PII,
no new secret-handling surface.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] New bounded context (`engineering_metrics`): domain (`CiRunCompletedReport`
      DTO, `compute_median`/`compute_ci_success_rate`), adapters (ORM models,
      repository), application service, API endpoint, Alembic branch (2 tables,
      no outbox) — all wired into `worker.py` (own consumer group
      `engineering-metrics-worker`, no relay task by design).
- [x] Confirmed no upstream change was needed to `pr_analysis`/`test_intelligence`
      — raw ingestion payloads already carry every required field.
- [x] `ruff check .` / `mypy .` (full-repo scope) clean.
- [x] Full test suite passing (274/274 at close, up from 256 before this
      sub-stage), 92% overall coverage maintained.
- [x] Worker health server smoke-tested locally (`/healthz`/`/readyz`) with the
      new consumer group wired in; full Kafka-connected smoke-test blocked by a
      host-vs-docker-network advertised-listener limitation unrelated to this
      sub-stage's code (affects any of the 6 consumer groups run this way, not
      specific to this change) — not re-litigated here.

## Changelog

| Date | Change |
|---|---|
| 2026-07-07 | Initial implementation: new `engineering_metrics` bounded context (domain, 2-table schema, repository, application service, read API), wired as a new consumer group in `worker.py`. Closed the 9.7 deferral by narrowing scope to PR-flow + CI-health aggregation; full DORA remains deferred for a documented reason (no deployment ingestion source). |
