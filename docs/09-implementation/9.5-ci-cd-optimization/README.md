# Sub-stage 9.5 — CI/CD Optimization

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation), 9.3 (Flaky Detection)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Serves Persona #2 from `docs/01-problem-discovery/README.md` (platform/CI-owning
engineer) — secondary/indirect evidence per `docs/02-product-discovery/README.md`
(Phase 2, not MVP), sharing the same underlying pain as Flaky Detection: without
a history-aware view, effort gets spent on guesswork. Here the specific
guesswork is optimizing the wrong thing — treating a consistently slow test
the same as a flaky one, when they need different remediation. This capability
answers "which tests are actually worth speeding up," reusing signal Phase 1
already collects rather than inventing a new integration surface.

## Scope

**In scope:**
- A `test_duration_signal` read-model, recomputed on every
  `ingestion.ci-run-completed` event (same trigger as Flaky Detection),
  tracking the **median** duration of each test over its most recent 20 runs.
- `GET /repositories/{owner}/{repo}/ci-cd/slow-tests` (Stage 5 addendum),
  scoped to the existing `read:test-intelligence` — ranks tests by median
  duration descending, **excluding** any test whose flakiness score exceeds
  0.2 (a "slow" test worth optimizing must be reliably slow, not flaky).
- **A real architectural decision made and logged before writing code**: this
  capability was never assigned a bounded context (Phase 2 capabilities
  weren't scoped by ADR-0002). Decided to add it as a third capability inside
  Test Intelligence rather than a new context — same test-run-history model
  already shared by Test Impact Analysis and Flaky Detection, no distinct
  ubiquitous language. Logged as an ADR-0002 addendum.
- **A real, latent Alembic tooling bug found and fixed**: `env.py` never set
  `include_schemas=True`, so autogenerate couldn't see already-existing
  tables in non-default schemas when diffing. Never surfaced before because
  this is the first incremental migration on an existing branch (every prior
  migration was either brand-new-branch or didn't need a second revision).
  Fixed; affects all 5 migration branches, not just this one. Logged as a
  Stage 4 addendum.

**Explicitly out of scope (this pass):**
- Any LLM-synthesized recommendation text (e.g., "consider splitting this
  test" or a narrative explanation) — this is a purely statistical ranking,
  consistent with Test Impact Analysis's and Flaky Detection's cost profile
  (no LLM), not PR Analysis's/Root Cause Analysis's. Revisit only if evidence
  emerges that a ranked list alone isn't actionable enough.
- Parallelization/bin-packing suggestions (e.g., grouping tests across CI
  workers to balance wall-clock time) — a genuinely different, larger-scoped
  algorithmic problem than ranking; tracked as a possible future extension,
  not assumed as part of "CI/CD Optimization" by default.
- A `test-intelligence.duration-updated` Kafka event — nothing downstream
  needs to react to a duration change today (unlike flakiness, which PR
  Analysis and Root Cause Analysis both consume for risk context). Publishing
  an event with no consumer is speculative infrastructure; add one if a real
  consumer appears.
- Configurable flaky-exclusion threshold or rolling-window size — 0.2 and 20
  runs are fixed MVP constants, matching the same class of decision already
  made in 9.3.

## Contracts consumed / amended

- Architecture: `docs/03-architecture/adr/0002-bounded-context-map.md` —
  addendum assigning this capability to Test Intelligence; cross-referenced
  in `docs/03-architecture/README.md`'s decisions log.
- Data model: `docs/04-database/README.md` (`test_intelligence.test_duration_signal`)
  — new addendum; also documents the `include_schemas=True` Alembic fix.
- API surface: `docs/05-api-design/openapi.yaml` — new `ci-cd-optimization`
  tag (documentation grouping only; implemented inside the `test_intelligence`
  Python package) and `GET .../ci-cd/slow-tests` operation; addendum logged
  in `docs/05-api-design/README.md`.

## Design notes specific to this sub-stage

- **Median, not average, for duration.** A single slow CI runner instance can
  spike one run's duration without the test itself being slow — median is the
  standard choice for latency-style metrics specifically because it isn't
  skewed by that kind of outlier the way a mean is (verified explicitly by a
  unit test using a 100x outlier that doesn't move the median at all).
- **"Slow but not flaky" is a query-time join, not a denormalized flag.**
  `test_duration_signal` and `test_stability_signal` are computed and owned
  independently — `list_slow_tests` does a `LEFT OUTER JOIN` at read time and
  filters out anything above the flaky threshold (or keeps it if no stability
  signal exists yet). This avoids two separate recompute paths needing to
  stay in sync on a shared field.
- **No new Kafka topic.** Every other analytical signal in this project that
  publishes an event has a real downstream consumer (flakiness → PR Analysis
  + Root Cause Analysis; impact → Root Cause Analysis). Slowness has none
  yet — adding a `test-intelligence.duration-updated` topic now would be
  infrastructure built for a consumer that doesn't exist, the same kind of
  premature investment this project has avoided elsewhere (e.g., no full-diff
  storage, no GitLab adapter without evidence).
- **`limit`-only pagination, not the cursor pattern used elsewhere.** Stage
  5's 2 existing list endpoints use cursor pagination because their
  collections grow unboundedly. This endpoint returns a bounded top-N
  ranking — a cursor has nothing left to page through once the ranking is
  exhausted, so matching the existing pattern here would be cargo-culted
  consistency, not a real need.
- **Alembic `include_schemas=True` fix.** Confirmed via `alembic heads`
  after the fix that all 5 branches still resolve to a single unambiguous
  head each, and the regenerated migration for this sub-stage's own table
  contained only the one genuinely new table (verified by reading the
  generated file before applying it).

## Test plan

Per `docs/08-testing-strategy/README.md`: 163 tests total (up from 146 at the
9.9 follow-ups), all passing; 93% overall coverage, all new modules at 100%
except `application.py` (98% — one defensive `sample_size == 0` guard mirrors
flakiness's equivalent structure but is structurally unreachable for duration,
since `duration_ms` always defaults to 0 rather than being absent).

- **Unit**: `compute_median_duration` (empty, single value, odd count, even
  count, and an explicit outlier-resistance case comparing what a mean would
  have done) in `tests/unit/test_intelligence/test_duration.py`.
- **Integration** (real Postgres): repository CRUD/upsert-idempotency for
  `test_duration_signal`; `list_slow_tests` explicitly tested for **excluding
  flaky tests**, **ordering by median duration descending**, **including a
  flakiness score when a stability signal exists** (vs. `null` when it
  doesn't), and **respecting `limit`**; the full `handle_ci_run_completed`
  flow recomputing the median across three CI runs on three different
  commits, and a test proving the duration and flakiness signals are computed
  independently of each other. Full API flow (200 with ranking, empty list,
  `limit` query param, 403 without scope).

## Observability

- No new structured log events or metrics beyond what `_recompute_duration`
  inherits implicitly from the existing `handle_ci_run_completed` call site
  (already logs `worker.test_intelligence.ci_run_processed`). Same deferral
  as every prior sub-stage on dedicated spans/metrics per signal.

## Security considerations

- Reuses the existing `read:test-intelligence` scope rather than minting a
  new one — this is read-only analytics over data already governed by that
  scope, and proliferating near-identical scopes for closely related
  analytics adds authorization surface without a real security benefit.
  Verified with a dedicated 403 test using a `read:pr-analysis` token.
- No new write path — the signal is derived entirely from already-ingested
  `test_case_result` data, no new caller-supplied-data trust boundary.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 163 tests passing, 93% overall coverage.
- [x] `test_intelligence` Alembic branch extended with a clean, isolated
      incremental migration (only the one new table), applied against a real
      Postgres, verified via `\dt` (8 tables) and `alembic heads` (all 5
      branches still resolve to a single head each).
- [x] ADR-0002 and Stage 4/5 addenda logged for the bounded-context decision,
      the new table, the new endpoint, and the Alembic tooling fix.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: `test_duration_signal` recompute wired into `handle_ci_run_completed` alongside flakiness, `GET .../ci-cd/slow-tests` ranking endpoint. Decided and logged CI/CD Optimization's bounded-context home (Test Intelligence, ADR-0002 addendum) before writing code. Found and fixed a latent Alembic bug (`include_schemas=True` missing) affecting all 5 migration branches, discovered by this sub-stage's incremental migration. |
