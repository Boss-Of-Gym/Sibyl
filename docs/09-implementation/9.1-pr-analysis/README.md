# Sub-stage 9.1 — PR Analysis

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation)
**Owner roles:** Senior Python Developer, Senior AI Engineer
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

First persona-facing MVP capability. Serves Persona #3 from
`docs/01-problem-discovery/README.md` (the ad hoc, single-person code-quality gate
with no synthesized signal behind it) and the MVP scope confirmed in
`docs/02-product-discovery/README.md`.

## Scope

**In scope:**
- Consuming `ingestion.pr-changed`, assembling a correlated risk-assessment
  context (diff metadata, no full diff content — per the Stage 4 ADR), calling
  `ReasoningPort.assess_pr_risk`, persisting the result, publishing
  `pr-analysis.completed`.
- `ReasoningPort` behind an interface (ADR-0005): a real adapter
  (`AnthropicReasoningPort`, structured tool-calling, Pydantic-validated output), a
  `FakeReasoningPort` for fast tests, and a `GuardedReasoningPort` implementing the
  Stage 6 §6 uniform LLM fallback contract (timeout/error/budget → fallback result,
  never blocks).
- `GET /repositories/{owner}/{repo}/pulls/{prNumber}/pr-analysis` (Stage 5), scoped
  to `read:pr-analysis`.
- `pr_analysis` schema tables (Stage 4 ERD): `pull_request`, `pr_risk_assessment`,
  `local_flaky_signal_projection` (created now, populated starting 9.3), its own
  `outbox_event`.
- A worker entrypoint (`src/sibyl/worker.py`) — the first real Kafka consumer,
  separate deployable from the API per ADR-0001.
- **Posting the result back to GitHub** (Checks API) — the last step of the Stage 6
  §1 diagram, added in a second pass once the core flow above was solid. GitHub App
  JWT-signing (RS256), installation-token exchange (Redis-cached per the Stage 4
  catalog), and `POST /repos/{repo}/check-runs` — split across a reusable
  `platform/github/` client (auth + Checks HTTP) and a PR-Analysis-specific
  notifier (`checks_notifier.py`) that maps a `RiskAssessment` to a check
  conclusion.

**Explicitly out of scope (this pass):**
- ~~`known_flaky_areas` in `PrRiskContext` is wired but always empty~~ — **closed
  2026-07-02, follow-up after 9.9**: `handle_pr_changed` now looks up
  `local_flaky_signal_projection` for the repository and matches flaky test
  identifiers to the PR's changed files via `pr_analysis/domain/flaky_matching.py`
  (same file-path/stem heuristic as 9.2's test-impact mapping, kept as its own
  copy per-context rather than shared, consistent with how `ReasoningPort` is
  also per-context). Only signals above `KNOWN_FLAKY_THRESHOLD` (0.2) count —
  `local_flaky_signal_projection` has a row for every test ever seen, including
  perfectly stable ones (9.3's "first computation always publishes" rule), so
  row-presence alone isn't "known flaky."
- Real LLM evaluation (golden-set scoring) — per Stage 8, that's a scheduled job
  against real credentials, not part of this build-out or its fast test suite.

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: `docs/05-api-design/openapi.yaml` (`pr-analysis` tag)
- Data model: `docs/04-database/README.md` (`pr_analysis` schema, Redis token-cache
  entry from the Stage 4 catalog)
- Runtime flow: `docs/06-sequence-diagrams/README.md` §1 (PR Analysis primary flow,
  including the GitHub Checks Adapter step), §6 (LLM fallback)
- Architecture: ADR-0003 (CQRS applied here), ADR-0005 (reasoning port design)

## Design notes specific to this sub-stage

- **Two bugs caught and fixed while building this, not after:**
  1. `alembic/env.py`'s `include_object` filter originally allow-listed table
     *names* per schema — broke the moment two schemas legitimately have a
     same-named table (`ingestion.outbox_event` vs. `pr_analysis.outbox_event`).
     Fixed to compare the table's actual `.schema` attribute instead — correct
     regardless of name collisions, and removes a manually-maintained list.
  2. `require_scope`'s FastAPI dependency read `Settings` via the globally-cached
     `get_settings()` rather than the specific `app.state.settings` instance
     `create_app()` was configured with. Invisible in production (one process, one
     `.env`), but silently broke test isolation and was architecturally wrong.
     Fixed with a `get_request_settings(request) -> Settings` dependency that reads
     from the actual app instance.
- **LLM guard is generic, not PR-Analysis-specific**: `guarded_llm_call` lives in
  `platform/reasoning_guard.py` precisely so Root Cause Analysis (9.9) reuses the
  same fallback contract per Stage 6's "one uniform contract" decision, rather than
  reimplementing it.
- **Worker logic is split from worker wiring**: every handler
  (`make_pr_changed_handler`, `make_pr_analysis_completed_handler`) and the
  `make_dispatcher` routing logic are standalone, testable functions; `run()` is
  just Kafka-consumer plumbing around them — otherwise the actual event-handling
  logic would only be exercisable through a live Kafka consumer loop.
- **GitHub API client split by concern, not by capability**: `platform/github/`
  (auth + Checks HTTP) is capability-agnostic — Root Cause Analysis (9.9) will
  reuse it to post its own check/comment without touching this code. Only the
  score→conclusion mapping in `checks_notifier.py` is PR-Analysis-specific domain
  knowledge.
- **Conclusion mapping is conservative about the fallback case**: when
  `explanation_unavailable` is true (LLM failed), the check conclusion is always
  `neutral`, never `success` — even though the fallback `RiskAssessment.score`
  defaults to `0.0`. A `0.0` score from a real assessment and a `0.0` placeholder
  from a failed LLM call are not the same claim, and conflating them would silently
  under-report risk exactly when the signal is least trustworthy.

## Test plan

Per `docs/08-testing-strategy/README.md`: 61 tests total (up from 27 at 9.0), all
passing; 90% overall coverage.

- **Unit**: context extraction from raw GitHub payload (incl. malformed-payload
  error), `FakeReasoningPort` scoring behavior, `GuardedReasoningPort` fallback on
  error/timeout/success, score→conclusion mapping, the worker's handler and
  dispatcher logic in isolation.
- **Contract** (`tests/contract/`, mocked HTTP via `httpx.MockTransport`, no real
  network): GitHub App JWT is correctly signed and verifiable with the App's public
  key; installation-token exchange request shape; token caching (second call makes
  zero HTTP requests); Checks API request shape; HTTP error propagation.
- **Integration** (real Postgres/Redis/Kafka via `testcontainers`): repository
  upsert/idempotency, full service flow (persists + publishes
  `pr-analysis.completed`), full API flow (200/404/403/401), the checks notifier
  against a real installation record with mocked GitHub HTTP.
- **Deliberately not tested here**: `AnthropicReasoningPort` itself (58% coverage —
  no live-provider calls in the fast suite, per Stage 8's LLM eval strategy).

## Observability

- Structured logs: `worker.pr_analysis.processed`, `worker.checks_notifier.processed`,
  `worker.unhandled_event_type` (a dispatcher safety net, not expected in normal
  operation).
- Traces/metrics: OTel wiring exists (from 9.0) but no PR-Analysis-specific spans
  or counters are emitted yet — deferred until enough consumers exist to make the
  right span boundaries obvious rather than guessed.

## Security considerations

- `read:pr-analysis` scope enforced via `require_scope` on the GET endpoint —
  verified by a 403 test with an insufficient-scope token and a 401 test with no
  token.
- No LLM prompt includes full diff content (only file paths + line-count deltas),
  limiting exposure if a diff contained something sensitive — consistent with the
  Stage 4 decision not to persist full diffs at all.
- GitHub App private key is read from a file path (`GITHUB_APP_PRIVATE_KEY_PATH`),
  never embedded in code or config — consistent with the Stage 7 secrets policy.
  Installation tokens are cached in Redis with the Stage-4-specified TTL, never
  persisted to Postgres.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code (verified by inspection).
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 61 tests passing, 90% overall coverage.
- [x] `pr_analysis` Alembic branch generated and applied against a real Postgres,
      verified via `\dt` (4 tables, no cross-schema name collision).
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.
- [x] GitHub Checks postback implemented and contract-tested — the MVP flow is now
      genuinely end-to-end, PR-visible (pending a real GitHub App installation to
      demo against).

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: domain model, ReasoningPort (fake/real/guarded), persistence, API endpoint, worker. Fixed two cross-cutting bugs (Alembic schema filter, settings resolution in auth). |
| 2026-07-02 | Added GitHub Checks postback: `platform/github/` (App auth + Checks client) and `pr_analysis/adapters/checks_notifier.py`. Worker now dispatches by event type across two topics. |
| 2026-07-02 | Follow-up after 9.9: closed the `known_flaky_areas` gap — `handle_pr_changed` now matches the PR's changed files against `local_flaky_signal_projection` via a new pure `flaky_matching.py`. |
| 2026-07-07 | Follow-up (launch-track Phase 1): backfilled `pr_risk_assessment.llm_tokens_used`/`llm_latency_ms` — frozen in the Stage 4 ERD since Stage 4, never actually implemented (the columns did not exist at all, not "existed but unpopulated" as earlier tracking assumed — corrected on investigation). `AnthropicReasoningPort` now reports `llm_tokens_used` from `response.usage`; latency is measured once, generically, inside the shared `platform/reasoning_guard.guarded_llm_call` (now returns `tuple[ResultT, latency_ms]`) rather than duplicated per adapter — `GuardedReasoningPort` applies it via `model_copy`. The same fix was applied to `root_cause_analysis` (see its own Changelog), which turned out to have the identical gap for `llm_latency_ms` despite being the presumed reference implementation. New migration `9b0b976f360a`. |
