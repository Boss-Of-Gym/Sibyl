# Sub-stage 9.3 — Flaky Detection

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Serves Persona #2 from `docs/01-problem-discovery/README.md` (platform/CI-owning
engineer distinguishing chronic flakiness from a one-off blip) — without a
history-aware view, a failing pipeline looks the same whether it's a genuinely
unstable test or a random blip, so remediation effort gets prioritized on
guesswork. Flaky Detection is the history-aware signal that answers that
question, and is the third input (alongside PR changes and test impact) that
Root Cause Analysis (9.9) will correlate. Confirmed MVP scope per
`docs/02-product-discovery/README.md`.

## Scope

**In scope:**
- Recomputing a per-test flakiness score from `test_case_result` history every
  time a new CI run completes, persisted to `test_stability_signal` (Stage 4
  schema, frozen empty since 9.2).
- Publishing `test-intelligence.flaky-signal-updated` only when the score change
  is **material** (see Design notes) — not on every recompute — to avoid
  flooding the event bus and the downstream PR Analysis projection with
  no-op updates.
- `GET /repositories/{owner}/{repo}/tests/{testIdentifier}/stability` (Stage 5),
  scoped to `read:test-intelligence`.
- Closing the loop into PR Analysis: a new Kafka consumer
  (`pr-analysis-worker`) upserts `local_flaky_signal_projection` (Stage 4
  schema, created empty in 9.1) whenever a signal materially changes — this is
  the local, read-only copy PR Analysis uses to populate
  `PrRiskContext.known_flaky_areas` (closed 2026-07-02 as a follow-up after
  9.9, see the 9.1 sub-stage doc's changelog — was deferred at the time this
  doc was originally written).
- **A real, un-planned routing bug found and fixed during this sub-stage**: the
  `testIdentifier` path parameter is a pytest node ID
  (`tests/test_x.py::test_x`), which always contains a literal `/`. The Stage 5
  OpenAPI draft declared it as a plain `string` path parameter, which
  Starlette/FastAPI match with a converter that stops at `/` — the route would
  have 404'd on every real identifier, not just missing ones. Fixed by matching
  `testIdentifier` as a greedy path segment (`{testIdentifier:path}`); see the
  Stage 5 addendum below.

**Explicitly out of scope (this pass):**
- ~~Actually populating `PrRiskContext.known_flaky_areas`~~ — **closed
  2026-07-02, follow-up after 9.9** (see the 9.1 sub-stage doc).
- Any UI/notification surfacing of flakiness (e.g. annotating a GitHub Check
  with "this test is known-flaky") — PR Analysis's checks notifier posts a
  risk assessment, not a flakiness-specific annotation; still not built,
  independent of the `known_flaky_areas` fix above.
- Configurable flakiness thresholds or scoring windows — the 0.05 materiality
  threshold and 20-run history window are fixed constants for MVP, not
  per-repository settings.

## Contracts consumed / amended

- API surface: `docs/05-api-design/openapi.yaml` (`test-intelligence` tag,
  `getTestStability` operation) — amended with a routing-behavior note; see the
  Stage 5 addendum in `docs/05-api-design/README.md`.
- Data model: `docs/04-database/README.md` (`test_intelligence.test_stability_signal`,
  `pr_analysis.local_flaky_signal_projection`) — both tables already existed
  (frozen empty) since 9.1/9.2; no schema change needed, only population.
- Runtime flow: no dedicated Stage 6 sequence diagram existed for Flaky
  Detection specifically; this sub-stage follows the same "consume Kafka event,
  recompute, conditionally publish" shape already established by 9.2's impact
  computation.

## Design notes specific to this sub-stage

- **Flakiness heuristic**: `2 * min(pass_count, fail_count) / sample_size` over
  the most recent 20 decisive (`passed`/`failed`) results for a given
  `(repository, test_identifier)`. `skipped` results are excluded from the
  sample entirely — they carry no pass/fail signal. This heuristic is
  deliberately simple and symmetric: an all-passing or all-failing test scores
  `0.0` (stable, even if the constant failure is a real regression — flakiness
  and regression are different signals, not conflated here), while a
  test split evenly between pass/fail scores `1.0` (maximally flaky). Pure
  function (`domain/flakiness.py`), no I/O, exhaustively unit tested.
- **Materiality gate, not "publish on every recompute."** Every CI run
  recomputes and persists the signal (so `GET .../stability` is always current),
  but `test-intelligence.flaky-signal-updated` is only published when
  `abs(new_score - previous_score) > 0.05`, or when no previous score existed
  (first-ever computation always publishes). Without this gate, a test with a
  stable history would still re-publish an identical event on every single CI
  run, which would flood the PR Analysis projection and Kafka topic with
  no-op churn for no benefit — the projection only needs to change when the
  *signal* meaningfully changes.
- **Why 0.05 and not 0, or a smaller epsilon**: with the 20-run window, the
  score can only take values in increments of `2/20 = 0.1` once the window is
  full, so any actual change in the underlying pass/fail mix moves the score by
  at least `0.1` — safely above the `0.05` threshold. The threshold exists to
  suppress floating-point noise and to make the *intent* ("material" vs.
  "any") explicit in code, not because smaller real deltas are expected at this
  window size. If the window size ever becomes configurable, this constant
  needs to move to scale with it.
- **`testIdentifier` routing bug, found while writing the API test, not the
  original design.** `docs/05-api-design/openapi.yaml`'s own example value for
  the parameter (`tests/test_checkout.py::test_applies_discount`) already
  contained a `/`, which should have been the tell at Stage 5 — a plain
  `{testIdentifier}` path segment cannot contain a literal `/` under
  Starlette's default `str` converter. Verified directly: a request path built
  from a real identifier does not match the route at all with the default
  converter (confirmed via `starlette.routing.compile_path`), so the endpoint
  would have silently 404'd for every real caller, not just genuinely-missing
  signals — indistinguishable from "no signal exists yet" from the outside.
  Fixed by using FastAPI/Starlette's `:path` converter
  (`{testIdentifier:path}`), which greedily matches everything up to the fixed
  `/stability` suffix. Rejected alternative: requiring clients to
  percent-encode `/` as `%2F` — this pushes a server routing detail onto every
  caller, and most HTTP clients (including simple `curl`/`httpx` calls) don't
  percent-encode path segments by default, so it would fail in practice the
  same way it was failing before.
- **Bidirectional projection stays a dumb copy.** `upsert_local_flaky_signal`
  in PR Analysis's repository does no interpretation of the score — it is a
  plain read-side projection, consistent with ADR-0002 (contexts never read
  each other's tables directly; they consume events and keep their own local
  copy). The interpretation (what counts as "known flaky" for risk purposes) is
  deliberately deferred, see Out of scope.

## Test plan

Per `docs/08-testing-strategy/README.md`: 108 tests total (up from 84 at 9.2),
all passing; 92% overall coverage maintained, `test_intelligence` at 100%.

- **Unit**: `compute_flakiness` (all-pass, all-fail, even split, low-flakiness,
  skipped-exclusion, empty history) and `is_material_change` (first
  computation, small delta, large delta) — `tests/unit/test_intelligence/test_flakiness.py`.
- **Integration** (real Postgres): repository methods
  (`get_recent_statuses` ordering and per-test-identifier scoping,
  `upsert_stability_signal` create/update) —
  `tests/integration/test_flaky_detection_repository.py`; the full
  recompute-and-conditionally-publish flow through
  `handle_ci_run_completed`, explicitly covering **first-run-always-publishes**,
  **repeated-stable-result-does-not-republish** (the actual materiality-gate
  claim, verified not just asserted), **alternating-results-raise-score-and-republish**,
  and **skipped-only-history-creates-no-signal** —
  `tests/integration/test_flaky_detection_service.py`; the
  `GET .../stability` endpoint (200/404/403, including the slash-containing
  identifier that exercises the routing fix) —
  `tests/integration/test_test_stability_api.py`; the new worker handler
  projecting into `local_flaky_signal_projection`, both insert and update paths
  — appended to `tests/unit/test_worker.py`.

## Observability

- Structured logs: `worker.pr_analysis.flaky_signal_projected`. Same deferral
  as 9.0/9.1/9.2 on spans/metrics.

## Security considerations

- `GET .../stability` is scoped to `read:test-intelligence`, consistent with
  the other test-intelligence read endpoints; verified with a dedicated 403
  test using a token scoped only to `read:pr-analysis`.
- No new write-capable endpoint or scope introduced — flakiness signals are
  derived entirely server-side from already-ingested `test_case_result` data,
  so there is no new caller-supplied-data trust boundary to defend (unlike
  9.2's `/ingest/test-results`, which does accept caller-supplied results).

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 108 tests passing, 92% overall coverage.
- [x] Stage 5 addendum logged for the `testIdentifier` routing gap.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: `compute_flakiness`/`is_material_change` pure functions, `test_stability_signal` recompute wired into `handle_ci_run_completed`, `GET .../stability` endpoint, `local_flaky_signal_projection` consumer in PR Analysis/worker. Found and fixed a real routing bug: `testIdentifier` (a pytest node ID) contains `/`, which the default path-string converter can't match — switched to `{testIdentifier:path}`, logged as a Stage 5 addendum. |
| 2026-07-02 | Follow-up after 9.9: `known_flaky_areas` deferral closed in PR Analysis (see 9.1 sub-stage doc). |
