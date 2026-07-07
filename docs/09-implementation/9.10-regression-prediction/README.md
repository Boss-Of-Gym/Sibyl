# Sub-stage 9.10 — Regression Prediction

**Status:** `APPROVED` (2026-07-07)
**Depends on:** 9.0 (Platform Foundation), 9.2 (Test Impact Analysis), 9.9 (Root Cause Analysis)
**Owner roles:** Senior Python Developer, Senior AI Engineer
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

No Stage 1 persona evidences this directly — `docs/02-product-discovery/README.md`
places it in the "market/competitive only" evidence tier, the same tier as
9.6/9.8/9.14/9.15. Justified for inclusion as a natural extension of Phase 1's
signal (reuses Test Impact Analysis's and Root Cause Analysis's already-collected
data) rather than direct persona evidence. Per `docs/09-implementation/README.md`'s
own Priority column, this is a **Phase 2** capability (the same tier as 9.7), not
Phase 3 — it was briefly mis-sequenced alongside the Phase 3 capabilities in
`docs/OPERATIONS_STRATEGY.md` before being corrected; unlike 9.7, it had no
legitimate blocking reason to defer, so it was built next per this project's own
priority-before-dependency-order build rule.

## Scope

- In scope: predicting the probability that a new pull request introduces a
  regression, grounded in historical Root Cause Analysis data for the files it
  touches. Correlates two signals (the PR's changed files, from the same
  `ingestion.pr-changed` event PR Analysis already consumes; and a local
  historical index of past root-cause hypotheses by file path) and calls an LLM
  through the same `ReasoningPort`/`GuardedReasoningPort`/`AnthropicReasoningPort`
  shape as PR Analysis and Root Cause Analysis. Publishes a completion event and
  posts a GitHub Check, mirroring both MVP capabilities exactly.
- Explicitly out of scope (this pass):
  - A bespoke statistical/ML prediction model — no ADR (including ADR-0005)
    establishes an ML training/serving pattern for this project; the existing
    LLM-reasoning-over-correlated-signal shape fits this problem without
    inventing new infrastructure for one weakly-evidenced capability.
  - Test Impact Analysis's `test_impact_projection`/affected-tests signal as a
    direct model input — the historical-regression-by-file-path signal alone was
    judged sufficient for a first version; extending the context with test-impact
    correlation is a real, undecided future enhancement, not assumed here.
  - On-call alerting or any operational hardening beyond what already exists
    generically (consumer retry/DLQ, from the launch-track Phase 1 work).

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: `docs/05-api-design/openapi.yaml` — new
  `GET /repositories/{owner}/{repo}/pulls/{prNumber}/regression-prediction`
  endpoint, new `read:regression-prediction` scope (new bounded context, so a new
  scope is correct — reusing another context's scope would be an authorization
  leak, per the same reasoning 9.6 established).
- Data model: `docs/04-database/README.md` — new seventh schema
  `regression_prediction` (`regression_prediction` result table,
  `historical_regression_projection` local projection, own outbox). Required
  amending the already-frozen `root-cause.hypothesis-ready` payload to add a
  nullable `suspected_file_path` field.
- Runtime flow: `docs/06-sequence-diagrams/README.md` §12 — two independently
  triggered flows into the same bounded context (index-build from
  `root-cause.hypothesis-ready`, predict-and-postback from `ingestion.pr-changed`),
  not a multi-input correlation join like Root Cause Analysis's own §4.
- Bounded-context decision: `docs/03-architecture/adr/0002-bounded-context-map.md`
  addendum — new, seventh bounded context. Full ubiquitous-language evaluation
  (against both `test_intelligence` and `root_cause_analysis` as join candidates)
  recorded there, not repeated here.

## Design notes specific to this capability

- **Why a new bounded context, not a join**: this capability's two dependencies
  (Test Impact Analysis, Root Cause Analysis) live in two *different* existing
  contexts — there's no single "join the context my dependencies already live in"
  option the way there was for 9.4/9.5/9.8. Running the same ubiquitous-language
  evaluation used for every prior addendum against both candidates concluded
  neither shares real domain language with this capability (see the ADR-0002
  addendum for the full reasoning). Architecturally, this makes Regression
  Prediction a much closer structural sibling of the MVP capabilities themselves
  than of anything in Phase 2.
- **`llm_tokens_used`/`llm_latency_ms` built in from day one** — unlike PR
  Analysis (9.1) and Root Cause Analysis (9.9), which both shipped without these
  columns and needed a launch-track Phase 1 backfill, this capability's schema
  and adapters include them from the first migration. Latency is measured
  generically by the shared `platform/reasoning_guard.guarded_llm_call` (built
  during that same backfill), so this capability gets `llm.call` span/metric
  instrumentation for free.
- **Historical index is a local projection, not a cross-schema read** — per
  ADR-0002's no-cross-schema-reads rule, `historical_regression_projection`
  mirrors the subset of Root Cause Analysis's hypothesis history this capability
  actually needs (file path, hypothesis text, confidence, occurrence time),
  built by consuming `root-cause.hypothesis-ready`. Rows with no
  `suspected_file_path` carry no signal for a by-file lookup and are skipped,
  not stored with a null path.
- **No new exception hierarchy** — the malformed-payload exception
  (`MalformedPrChangedPayload`) now inherits from the shared
  `platform.events.errors.MalformedEventError`, the same type the launch-track
  Phase 1 consumer retry/DLQ mechanism checks for. This is the first sub-stage
  built *after* that mechanism existed; every malformed-payload exception in
  this codebase should inherit from it going forward so dead-lettering works
  correctly without a per-context special case.
- **Prediction rows are append-only, not upserted** — like `pr_risk_assessment`/
  `root_cause_hypothesis`, "latest" is whichever row has the newest
  `computed_at`, not a keyed upsert.

## Test plan

Per `docs/08-testing-strategy/README.md`: unit tests for `FakeReasoningPort`'s
heuristic and `GuardedReasoningPort`'s fallback/timeout/schema-validation-failure
branches (mirroring the pattern established for PR Analysis/Root Cause Analysis);
integration tests (real Postgres via testcontainers) for the repository layer,
the service's two handlers (including the malformed-payload and
historical-index-then-prediction correlation paths), the GitHub Checks postback
(contract-tested via `httpx.MockTransport`, mirroring
`test_root_cause_checks_notifier.py`), and the read API (200/404/403). The real
`AnthropicReasoningPort` adapter is not unit-tested directly — same accepted
pattern as `pr_analysis`/`root_cause_analysis`'s equivalent adapters (58%
coverage, exercised only via the golden-set eval harness against a real key).

## Observability

`llm.call` span and its 6 metrics (`llm.budget_exceeded_total`/`timeout_total`/
`provider_error_total`/`schema_validation_failed_total`/`success_total`/
`latency_ms`/`tokens_used`) come for free from the shared
`platform.reasoning_guard.guarded_llm_call`. `consumer.process` span and
`consumer.processed_total` come for free from `worker.make_dispatcher`. No new
per-capability named counters (e.g. `regression_prediction.completed_total`)
were added in this pass — tracked as the same mechanical follow-up already
logged for every other capability's named counters in
`docs/OPERATIONS_STRATEGY.md`.

## Security considerations

New `read:regression-prediction` scope, correctly not reused from another
context (new bounded context). No new data sensitivity beyond what Root Cause
Analysis and PR Analysis already handle (repository names, file paths, LLM-
generated rationale text) — no new PII, no new secret-handling surface.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] New bounded context (`regression_prediction`): domain, adapters
      (Anthropic/Guarded/Fake reasoning ports, repository, checks notifier), API,
      application service, Alembic branch — all present and wired into `worker.py`
      (own consumer group `regression-prediction-worker`, own outbox relay task,
      checks postback added to the existing `pr-analysis-worker` group).
- [x] `root-cause.hypothesis-ready` payload amended with `suspected_file_path`;
      confirmed no existing consumer breaks (checked: the GitHub Checks postback
      ignores unknown fields).
- [x] `ruff check .` / `mypy .` (full-repo scope) clean.
- [x] Full test suite passing (256/256 at close, up from 234 before this
      sub-stage), 92% overall coverage maintained.
- [x] Full `worker.py` process smoke-tested locally against the real
      docker-compose Postgres/Redis/Kafka stack — starts cleanly with all 6
      consumer groups, 5 relay loops, and the health server running together.

## Changelog

| Date | Change |
|---|---|
| 2026-07-07 | Initial implementation: new `regression_prediction` bounded context (domain, 3-table schema, repository, LLM adapters, checks notifier, application service, API endpoint), wired as a new consumer group in `worker.py`. Amended the frozen `root-cause.hypothesis-ready` payload to add `suspected_file_path`. Built with `llm_tokens_used`/`llm_latency_ms` from day one, unlike the two MVP contexts that needed a later backfill. |
