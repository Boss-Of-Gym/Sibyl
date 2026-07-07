# Sub-stage 9.9 — Root Cause Analysis

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation), 9.1 (PR Analysis), 9.2 (Test Impact Analysis), 9.3 (Flaky Detection)
**Owner roles:** Senior Python Developer, Senior AI Engineer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Serves Persona #1 from `docs/01-problem-discovery/README.md` (SDET/QA Engineer
triaging a failing test) — the pain is specifically that even with solid test
logging, determining *where in the code* a failure actually originates
requires manual archaeology through the codebase's structure, every time.
Root Cause Analysis is the capability that does that correlation
automatically, by combining the three signals the platform has already built:
what changed in the PR (9.1), which tests that change was expected to affect
(9.2), and whether the failing test is a known flake (9.3). Confirmed MVP
scope per `docs/02-product-discovery/README.md`, and the last of the four
confirmed-MVP capabilities to be built.

## Scope

**In scope:**
- A new `root_cause_analysis` bounded context: consumes `ingestion.ci-run-completed`
  (to detect test failures), `pr-analysis.completed`, `test-intelligence.impact-computed`,
  and `test-intelligence.flaky-signal-updated`; correlates all three signals for
  a given failing test and calls `ReasoningPort.explain_root_cause(...)` to
  produce a hypothesis.
- `GET /repositories/{owner}/{repo}/failures/{failureEventId}/root-cause`
  (Stage 5), scoped to `read:root-cause` — 200 with the hypothesis, 202 if not
  computed yet, 404 if the failure event doesn't exist for that repository.
- Publishing `root-cause.hypothesis-ready` once a hypothesis is computed.
- **Three real, un-planned gaps found and fixed before writing any correlation
  code** (all logged as addenda — see Contracts consumed below):
  1. Stage 6's diagram had Ingestion write `failure_event` directly into
     `root_cause_analysis`'s Postgres schema — violates the same
     cross-schema-write rule this project enforces everywhere else, and
     Ingestion has no per-test pass/fail data to act on regardless (that
     lives in Test Intelligence, per the 9.2 addendum). Fixed: Root Cause
     Analysis is now its own consumer of `ingestion.ci-run-completed` and
     builds `failure_event` rows itself.
  2. Stage 4's `root_cause_analysis` ERD had no local projections for the
     other two contexts' events it needs to correlate against — every other
     analytical context already has this pattern (`pr_changed_files_projection`,
     `local_flaky_signal_projection`). Fixed: added `pr_context_projection`
     and `test_impact_projection`.
  3. The Stage 9 roadmap's own description of this capability ("correlates PR
     changes, test impact, **and flakiness signal**") was never actually wired
     into the Stage 4 Kafka catalog — Root Cause Analysis was not listed as a
     consumer of `test-intelligence.flaky-signal-updated`. Fixed: added
     `flaky_signal_projection`, mirroring PR Analysis's existing pattern.
- **A mechanism refinement, by the same precedent as 9.2's buffer-and-poll
  replacement**: the diagram's 2-minute join timeout with a "partial context,
  lower confidence" fallback was replaced with deterministic, bidirectional-style
  correlation extended to three inputs — whichever of `failure_event`,
  `pr_context_projection`, or `test_impact_projection` arrives last for a given
  failure triggers computation. See Design notes for why this is sound (not
  just convenient).

**Explicitly out of scope (this pass):**
- ~~Posting the hypothesis to GitHub (a Checks-adapter consumer of
  `root-cause.hypothesis-ready`)~~ — **closed 2026-07-02, same-day follow-up**:
  `root_cause_analysis/adapters/checks_notifier.py` (`RootCauseChecksNotifier`)
  posts a check run summarizing the hypothesis, consistent with how 9.1 added
  its own Checks postback as a follow-up rather than blocking the sub-stage's
  initial close on it. Required extending the `root-cause.hypothesis-ready`
  payload with `head_sha` (needed by the Checks API, not originally included)
  and `explanation_unavailable` (so the notifier can render a clear fallback
  summary instead of an empty one).
- Multiple/refined hypotheses per failure — the ERD's `FAILURE_EVENT ||--o{
  ROOT_CAUSE_HYPOTHESIS` cardinality allows more than one hypothesis per
  failure over time, but this pass computes exactly one (idempotent — a
  second correlation trigger for an already-resolved failure is a no-op).
- Any UI/notification beyond the API + Kafka event + the one GitHub Check.

## Contracts consumed / amended

- API surface: `docs/05-api-design/openapi.yaml` (`root-cause-analysis` tag,
  `getRootCauseHypothesis` operation) — no changes needed, contract was
  already implementable as frozen.
- Data model: `docs/04-database/README.md` (`root_cause_analysis` schema) —
  addendum adding `pr_context_projection`, `test_impact_projection`,
  `flaky_signal_projection`, and two new Kafka consumer entries
  (`ingestion.ci-run-completed`, `test-intelligence.flaky-signal-updated`).
- Runtime flow: `docs/06-sequence-diagrams/README.md` §4 (Root Cause Analysis)
  — revised to remove the cross-schema write and replace the join-timeout
  with deterministic correlation; addendum logged in that doc's Decisions log.

## Design notes specific to this sub-stage

- **Why the 2-minute join timeout could be removed outright, not just
  shortened.** The platform's uniform LLM fallback contract (Stage 6 §6)
  guarantees `pr-analysis.completed` always eventually publishes (even on
  total LLM failure, with `explanation_unavailable=true`) — it is never
  silently absent for an open PR. Separately, `test-intelligence.impact-computed`
  is guaranteed for any commit that has both a `pr_changed_files_projection`
  row and at least one completed test run (9.2's bidirectional correlation) —
  and a `failure_event`'s existence *is* proof a test run completed for that
  exact commit. So for a real failing test on a real open PR, all three
  correlation inputs are structurally guaranteed to arrive eventually; a
  timeout has nothing genuine to guard against, only an arbitrary "what does
  lower confidence even mean, quantitatively" heuristic to introduce. The one
  case where correlation never completes — a CI run with no associated PR
  (e.g. a push straight to `main`) — is correct to never produce a
  PR-scoped hypothesis, the same reasoning 9.2 already established for test
  impact.
- **Correlation key resolution.** `failure_event` only carries `commit_sha`,
  not `pr_number` — Ingestion has no concept of PRs. `pr-analysis.completed`
  carries `head_sha`, so `pr_context_projection` is looked up by
  `(repository, head_sha)` to resolve which PR (if any) a failing commit
  belongs to; `test_impact_projection` is then looked up by the resolved
  `(repository, pr_number)`. This two-hop resolution is what the extra
  projection tables exist to support.
- **Idempotency, not "compute once and lock."** `_try_correlate` checks
  whether a hypothesis already exists for the failure event before doing any
  work; a correlation trigger firing again for an already-resolved failure
  (e.g. a duplicate or late-arriving event) is a cheap no-op rather than a
  race to guard against with a lock.
- **Flakiness signal is optional context, not a fourth required input.**
  Unlike the three inputs that gate correlation, `flaky_signal_projection` is
  read best-effort at correlation time — if it doesn't exist yet, `explain_root_cause`
  is still called with `flakiness_score=None`, since flakiness updates arrive
  independently of any specific failure and shouldn't block a hypothesis a
  human is waiting on.
- **`ReasoningPort` is per-context, not a shared class**, following the exact
  precedent PR Analysis already established: `root_cause_analysis/domain/ports.py`
  defines its own narrow `Protocol` (`explain_root_cause`), with its own
  `AnthropicReasoningPort` (tool-calling, schema-constrained), `FakeReasoningPort`,
  and `GuardedReasoningPort` (uniform timeout/error → `explanation_unavailable`
  fallback, per Stage 6 §6). The "shared kernel" (ADR-0002) is the *pattern*,
  not shared code — each context owns its own tool schema and prompt.
- **Noted but not fixed in this pass**: while implementing `root_cause_hypothesis`'s
  `llm_tokens_used` column (frozen in the Stage 4 ERD), found that
  `pr_analysis.pr_risk_assessment`'s equivalent `llm_tokens_used`/`llm_latency_ms`
  columns from the same ERD were never actually implemented back in 9.1 — a
  pre-existing gap between the frozen schema and the shipped code, unrelated
  to this sub-stage's scope. Flagged in `PROGRESS.md` as a follow-up rather
  than silently left unnoticed or fixed as an unrelated drive-by change here.

## Test plan

Per `docs/08-testing-strategy/README.md`: 146 tests total (136 at initial
close + 10 more from the same-day `known_flaky_areas`/Checks-postback
follow-ups), all passing; 93% overall coverage, `root_cause_analysis` at 100%
except `api.py` (a coverage-tool tracing artifact confirmed harmless — see
below, not a real gap).

- **Unit**: `FakeReasoningPort` and `GuardedReasoningPort` behavior (timeout,
  error, success passthrough), mirroring the existing PR Analysis test
  pattern exactly.
- **Integration** (real Postgres): repository CRUD/upsert-idempotency for all
  five tables; the full correlation flow with **all three arrival orders
  explicitly tested** (`test_failure_event_arriving_last_triggers_correlation`,
  `test_pr_context_arriving_last_triggers_correlation`,
  `test_test_impact_arriving_last_triggers_correlation`) — this is the actual
  claim the design notes make, verified per-ordering, not just asserted;
  idempotency (`test_correlation_does_not_recompute_once_a_hypothesis_exists`);
  the no-PR case never producing a hypothesis
  (`test_no_hypothesis_without_pr_context`); flakiness-signal presence/absence
  both explicitly asserted via a context-recording test double; passing tests
  never creating a `failure_event`. Full API flow (200/202/404 for missing
  failure event/404 for repository mismatch/403). Worker handler wiring for
  all four new consumer handlers plus the tri-way correlation exercised
  end-to-end through the actual handler functions, not just the service.
- **Follow-up tests (same day)**: `RootCauseChecksNotifier` (posts a check run
  for a known installation, falls back to a clear summary when
  `explanation_unavailable`, raises `UnknownInstallation` otherwise) using the
  same `httpx.MockTransport` contract-test pattern as `PrAnalysisChecksNotifier`;
  `match_known_flaky_areas` (exact-file match, stem match, below-threshold
  exclusion, unrelated-file exclusion, dedup/sort) in
  `tests/unit/pr_analysis/test_flaky_matching.py`; an integration test proving
  `handle_pr_changed` actually populates `PrRiskContext.known_flaky_areas`
  from `local_flaky_signal_projection` via a context-recording test double,
  plus the negative case (unrelated flaky test stays out of the list).
- A debug side-effect was temporarily inserted and confirmed the
  `get_root_cause_hypothesis` handler body executes correctly on every test
  (correct arguments, correct branch) before being reverted — the API
  endpoint's coverage tool reports 90% (lines 37-44 "missing") despite this
  confirmed execution; treated as a benign coverage-instrumentation artifact
  on this specific async-context-manager shape, not a real testing gap, since
  behavior was independently verified.

## Observability

- Structured logs: `worker.root_cause_analysis.ci_run_processed`,
  `worker.root_cause_analysis.pr_analysis_completed_processed`,
  `worker.root_cause_analysis.impact_computed_processed`,
  `worker.root_cause_analysis.flaky_signal_processed`. Same deferral as
  9.0–9.3 on spans/metrics (`root-cause.correlate` span,
  `root_cause.completed_total` metric named in the Stage 6 diagram are not
  yet wired to real OpenTelemetry/Prometheus calls).

## Security considerations

- `GET .../root-cause` is scoped to `read:root-cause`, consistent with the
  other analytical read endpoints; verified with a dedicated 403 test.
- The endpoint checks `failure_event.repository` against the requested
  `{owner}/{repo}` path and 404s on mismatch — a caller cannot probe for the
  existence of failure events in a repository/installation they don't have a
  matching path for, even with a valid `failureEventId` UUID from elsewhere
  (UUIDs aren't secret, so this check is defense in depth, not the primary
  access control — `read:root-cause` scope is).
- No new write-capable endpoint or scope introduced — failure events and
  hypotheses are derived entirely server-side from already-ingested/computed
  data, no new caller-supplied-data trust boundary.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 146 tests passing, 93% overall coverage.
- [x] `root_cause_analysis` Alembic branch generated and applied against a
      real Postgres, verified via `\dt` (6 tables).
- [x] Stage 4 and Stage 6 addenda logged for the three gaps and the
      correlation-mechanism refinement.
- [x] Both same-day follow-ups closed: `known_flaky_areas` in PR Analysis, and
      the GitHub Checks postback for `root-cause.hypothesis-ready`.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated, including the pre-existing 9.1 schema gap flagged
      as a follow-up.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: new `root_cause_analysis` bounded context (domain, 6-table schema, repository, LLM adapters, application service, API endpoint), wired as a 4-topic consumer group in `worker.py`. Found and fixed three gaps before writing correlation code (cross-schema write in the diagram, missing local projections in the Stage 4 ERD, flakiness signal never wired into the Kafka catalog) and replaced the diagram's 2-minute join timeout with deterministic tri-way correlation, extending the precedent set in 9.2. |
| 2026-07-02 | Same-day follow-up: closed `known_flaky_areas` in PR Analysis (`flaky_matching.py`, deferred since 9.3) and added the GitHub Checks postback for `root-cause.hypothesis-ready` (`RootCauseChecksNotifier`), extending the payload with `head_sha`/`explanation_unavailable`. |
| 2026-07-07 | Follow-up (launch-track Phase 1): while backfilling `pr_analysis`'s `llm_tokens_used`/`llm_latency_ms` gap, discovered this context had the same gap — `root_cause_hypothesis.llm_latency_ms` is in the Stage 4 ERD (`docs/04-database/README.md`) but was never implemented here either, despite this context being treated as the reference pattern for `llm_tokens_used`. Fixed: latency is now measured generically inside `platform/reasoning_guard.guarded_llm_call` and applied in `GuardedReasoningPort` via `model_copy`. New migration `2f4c9d2856af`. |
