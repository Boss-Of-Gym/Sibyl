# Sub-stage 9.11 — Release Risk Analysis

**Status:** `APPROVED` (2026-07-07)
**Depends on:** 9.4 (Coverage Intelligence), 9.7 (Engineering Metrics), 9.10 (Regression Prediction)
**Owner roles:** Senior Python Developer, Staff Backend Engineer
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

No Stage 1 persona directly evidences this capability by name —
`docs/02-product-discovery/README.md` places it in the "market/competitive
only" evidence tier, deliberately excluded from MVP because it fuses
signal that didn't exist yet at the time. Its dependencies (9.4/9.7/9.10)
are now all `APPROVED`. Re-reading Stage 1's persona 3 ("small-team release
decision-maker," first-hand evidence) shows the closest real pain is a
**merge-time decision** — "is it OK to ship right now" — which this
capability now has enough signal to support, scoped honestly to a per-PR
score rather than a literal release/deployment artifact this project has
no ingestion source for.

## Scope

- In scope: a fused, deterministic (no LLM) merge-readiness risk score for
  a specific pull request, computed from three already-built signals:
  Regression Prediction's per-PR regression probability, a repository's
  recent CI success rate (own local projection, most recent 20 runs), and
  average file coverage across the repository. Recomputed whenever a
  Regression Prediction result arrives for that PR. Published as
  `release-risk.completed` and exposed via
  `GET /repositories/{owner}/{repo}/pulls/{prNumber}/release-risk`.
- Explicitly out of scope (this pass):
  - Any LLM-generated narrative or go/no-go recommendation — that is
    9.12 Release Advisor's own frozen scope, not this one's. 9.11 produces
    a number and which signals fed it; it does not explain or recommend.
  - A literal "release" or deployment entity — no deployment/tag ingestion
    exists anywhere in this project (the same gap that keeps full DORA
    deferred under 9.7). Scored per-PR instead, per the honest scoping
    decision above.
  - Configurable/weighted-by-user scoring — the three signals are equally
    weighted and any missing signal is simply excluded from the average
    (renormalized over what's available), not assumed worst- or best-case.
    Tunable weighting is a real, undecided future enhancement.

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: `docs/05-api-design/openapi.yaml` — new
  `GET /repositories/{owner}/{repo}/pulls/{prNumber}/release-risk` endpoint,
  new `read:release-risk` scope (new bounded context, so a new scope is
  correct, per the same reasoning 9.6/9.10/9.7 established).
- Data model: `docs/04-database/README.md` — new ninth schema
  `release_risk_analysis` (`regression_signal_projection`,
  `ci_health_projection`, `coverage_signal_projection`,
  `release_risk_assessment`, own outbox). Required amending the
  already-frozen `test_intelligence` Stage 4 contract to add
  `test-intelligence.coverage-computed`.
- Runtime flow: `docs/06-sequence-diagrams/README.md` §14 — three
  independent projection paths feeding one assessment trigger, and the §9
  addendum showing where the new coverage event is now published.
- Bounded-context decision: `docs/03-architecture/adr/0002-bounded-context-map.md`
  addendum — new, ninth bounded context. Full three-way ubiquitous-language
  evaluation (against Coverage Intelligence, Engineering Metrics, and
  Regression Prediction as join candidates) recorded there, not repeated
  here.

## Design notes specific to this capability

- **Why a new bounded context, not a join**: dependencies span three
  different existing contexts, not one or two — a stronger version of the
  fan-in test that already split Regression Prediction (9.10) out on its
  own. Fusing three genuinely different facts into one new fact
  ("is this PR safe to ship") is itself evidence of a new bounded context.
- **No LLM in this capability** — `compute_release_risk_score` is a
  deterministic weighted average, matching Engineering Metrics's (9.7)
  pure-statistics shape. The LLM-generated narrative is explicitly
  reserved for 9.12 Release Advisor per its own frozen roadmap text.
- **Three signals, three different acquisition patterns, all avoiding
  cross-schema reads**: Regression Prediction's completion event is
  consumed directly (the ordinary case); CI health is computed from this
  context's *own* local projection of the raw `ingestion.ci-run-completed`
  topic, rather than depending on Engineering Metrics's schema or API at
  all; coverage required amending Test Intelligence's frozen contract to
  publish a new `test-intelligence.coverage-computed` event, since none
  existed — the same class of change as 9.10's `suspected_file_path`
  amendment to `root-cause.hypothesis-ready`.
- **Recomputation trigger**: `regression-prediction.completed`, not the
  earliest-arriving signal — mirrors Root Cause Analysis's own
  multi-input-correlation pattern (§4), reading already-materialized local
  projections for the other two inputs rather than racing them.
- **Recent-N vs. calendar-window convention, deliberately different from
  Engineering Metrics**: CI health uses the most recent 20 runs
  (`get_recent_ci_runs`), mirroring Test Intelligence's own
  `get_recent_statuses`/`get_recent_durations` fixed-sample-size
  convention — appropriate for a recency-weighted reliability signal
  feeding a decision score, distinct from Engineering Metrics's
  calendar-day reporting window, which answers a differently-shaped
  question.
- **Graceful degradation on missing signal**: `compute_release_risk_score`
  averages only the signals actually present (`considered_signals` records
  which), rather than fabricating a worst-case or best-case value for
  data that hasn't arrived yet (e.g. no CI runs recorded for a brand-new
  repository).
- **Append-only assessments**: like `regression_prediction`/
  `pr_risk_assessment`, a new assessment is a new row; "latest" is the
  newest `computed_at`, not a keyed upsert.
- **Outbox with no current consumer, justified**: unlike `test_duration_signal`'s
  deliberately-unbuilt event (Stage 9.5 addendum — genuinely no planned
  consumer), `release-risk.completed` has a named, frozen future consumer
  (9.12 Release Advisor) — not speculative infrastructure.

## Test plan

Per `docs/08-testing-strategy/README.md`: unit tests for
`compute_ci_success_rate`/`compute_average_coverage_pct`/
`compute_release_risk_score` (empty input, single/mixed signal
availability, all-three-present weighted average, graceful degradation);
integration tests (real Postgres via testcontainers) for the repository
layer (upsert-then-update semantics per projection, recency-ordering and
limit for `get_recent_ci_runs`), the service's three handlers (including
the fused-assessment computation with all three signals present, and with
only the regression signal present), the read API (200/404/403), and an
amendment to Test Intelligence's own coverage service test confirming
`test-intelligence.coverage-computed` is published per file.

## Observability

`consumer.process` span and `consumer.processed_total` come for free from
`worker.make_dispatcher`, same as every other consumer group. No LLM call,
so none of the `llm.*` metrics apply — matching Engineering Metrics (9.7).
No new per-capability named counters were added in this pass, tracked as
the same mechanical follow-up already logged for every other capability's
named counters in `docs/OPERATIONS_STRATEGY.md`.

## Security considerations

New `read:release-risk` scope, correctly not reused from another context
(new bounded context). No new data sensitivity — repository names, PR
numbers, and already-computed numeric signals; no new PII, no new
secret-handling surface.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] New bounded context (`release_risk_analysis`): domain
      (`compute_ci_success_rate`/`compute_average_coverage_pct`/
      `compute_release_risk_score`, local `CiRunCompletedReport` DTO),
      adapters (ORM models, repository), application service, read API,
      Alembic branch (4 tables + outbox) — all wired into `worker.py` (own
      consumer group `release-risk-analysis-worker`, own outbox relay task).
- [x] Amended Test Intelligence's frozen Stage 4 contract to publish
      `test-intelligence.coverage-computed`; confirmed via a new assertion
      in the existing coverage service test.
- [x] `ruff check .` / `mypy .` (full-repo scope) clean.
- [x] Full test suite passing (296/296 at close, up from 274 before this
      sub-stage), 92% overall coverage maintained
      (`release_risk_analysis` itself at 100%).
- [x] Worker health server smoke-tested locally (`/healthz`/`/readyz`) with
      the new consumer group and relay task wired in.

## Changelog

| Date | Change |
|---|---|
| 2026-07-07 | Initial implementation: new `release_risk_analysis` bounded context (domain, 4-table + outbox schema, repository, application service, read API), wired as a new consumer group and relay task in `worker.py`. Amended Test Intelligence's frozen `handle_coverage_report_received` to publish `test-intelligence.coverage-computed`. Scoped "release" honestly to a per-PR merge-readiness score, consistent with Stage 1's actual persona evidence and the absence of any deployment/tag ingestion source. |
