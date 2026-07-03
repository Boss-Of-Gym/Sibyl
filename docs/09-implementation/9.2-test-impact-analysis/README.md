# Sub-stage 9.2 — Test Impact Analysis

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation), 9.1 (PR Analysis)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Serves Persona #1 from `docs/01-problem-discovery/README.md` (SDET tracing a test
failure back to its cause) — Test Impact Analysis is the piece that answers "what
did this change plausibly affect," which Root Cause Analysis (9.9) will later
consume alongside Flaky Detection (9.3) signal. Confirmed MVP scope per
`docs/02-product-discovery/README.md`.

## Scope

**In scope:**
- Mapping a PR's changed files to previously-observed tests likely affected by the
  change, published as `test-intelligence.impact-computed`.
- `GET /repositories/{owner}/{repo}/pulls/{prNumber}/test-impact` (Stage 5), scoped
  to `read:test-intelligence`.
- **A real, un-planned architecture gap found and fixed during this sub-stage**:
  `POST /ingest/test-results` — a new CI-job-facing endpoint, because GitHub's
  native `check_suite`/`workflow_run` webhook has no per-test data (only a
  suite-level conclusion), and the Stage 4 `test_case_result` schema needs
  per-test granularity. See the Stage 4/5 addenda below — this is not a local
  decision, it changes where `ingestion.ci-run-completed` actually comes from.
- The `test_intelligence` schema (7 tables per the Stage 4 ERD, including
  `test_stability_signal`, empty until 9.3 — same "create the frozen schema now,
  populate later" precedent as 9.1's `local_flaky_signal_projection`).
- Bidirectional event correlation: `ingestion.pr-changed` and
  `ingestion.ci-run-completed` can arrive in either order; whichever arrives
  second triggers the impact computation. This **replaces** the Stage 6 §2
  diagram's "buffer and poll for up to 5 minutes" sketch with a simpler,
  deterministic mechanism — see Design notes.

**Explicitly out of scope (this pass):**
- Flaky Detection (`test_stability_signal` population) — sub-stage 9.3.
- Import-graph or coverage-based impact analysis — the mapping heuristic here is
  deliberately simple (test-file-changed-directly, or source-file/test-file share
  a name stem) against *previously observed* test identifiers for the repository.
  This is an honest MVP simplification: no static analysis of the repo's source
  tree is performed (would require cloning the repo, out of scope), and "affected"
  is bounded to tests we've already seen run at least once.
- CI-job tooling to actually call the new `/ingest/test-results` endpoint (e.g. a
  pytest plugin or a documented `ci.yml` step) — the endpoint and its contract
  exist and are tested; wiring *this project's own* CI to call it is a Stage
  10-ish or later-9.x follow-up, not blocking this sub-stage's completion.

## Contracts consumed / amended

- API surface: `docs/05-api-design/openapi.yaml` (`test-intelligence` tag), plus
  the new `/ingest/test-results` endpoint and `write:test-results` scope — an
  addendum to Stage 5, logged in `docs/05-api-design/README.md`.
- Data model: `docs/04-database/README.md` (`test_intelligence` schema) — addendum
  logged there correcting `ingestion.ci-run-completed`'s producer.
- Runtime flow: `docs/06-sequence-diagrams/README.md` §2 (Test Impact Analysis) —
  superseded in mechanism (not outcome) by the bidirectional-correlation design
  below.

## Design notes specific to this sub-stage

- **Bidirectional correlation instead of buffer-and-poll.** The original Stage 6
  sketch had the CI-run handler wait/retry for up to 5 minutes if the matching
  PR-changed context hadn't arrived yet. Implementation revealed a simpler,
  equally-correct alternative: **both** handlers (`handle_pr_changed` and
  `handle_ci_run_completed`) upsert their own data first, then check whether the
  *other* side's data already exists for the same `(repository, commit_sha)`; if
  so, that handler computes and publishes the impact. Whichever event arrives
  second is the one that triggers computation — no timeout to tune, no
  never-resolves edge case (if a CI run has no associated PR, e.g. a push to
  `main`, the impact is correctly never computed, and the raw test results are
  still stored for future use). This is a refinement of the diagram's mechanism,
  not a change to its guaranteed behavior (out-of-order tolerance) — logged here
  rather than silently deviating from an approved diagram.
- **Test Intelligence keeps its own local copy of PR-changed data**
  (`pr_changed_files_projection`), consistent with the ADR-0002 rule that contexts
  never join across schemas — PR Analysis already consumes `ingestion.pr-changed`
  independently; this is Test Intelligence's own Kafka consumer group on the same
  topic, not a shared subscription.
- **Impact mapping is a pure function** (`domain/mapping.py`), taking changed file
  paths and a list of previously-observed test identifiers, with no I/O — trivial
  to unit test exhaustively and to swap for a smarter heuristic later without
  touching the application service.
- **Installation resolution by organization login**: `/ingest/test-results` only
  has `owner/repo`, not an internal `installation_id` (unlike GitHub webhooks,
  which carry it). Resolved via a new `InstallationRepository.get_by_organization_login`,
  consistent with ADR-0006's single-tenant-per-deployment assumption. Fixed to
  return the most-recently-installed match rather than assuming strict uniqueness
  (a real bug caught by the test suite once multiple test-created installations
  shared an organization login — the fix is also more correct for a real
  reinstall-after-uninstall scenario).
- **Worker restructured to run multiple consumer groups concurrently**
  (`asyncio.gather`), one per logical service (`pr-analysis-worker`,
  `test-intelligence-worker`), both subscribing to `ingestion.pr-changed`
  independently — correct Kafka semantics (each consumer group gets its own full
  copy of a topic) while still deploying as the single `worker` process ADR-0001
  and the Stage 7 Helm chart assume.

## Test plan

Per `docs/08-testing-strategy/README.md`: 84 tests total (up from 61 at 9.1), all
passing; 92% overall coverage. Every `test_intelligence` module at 100%.

- **Unit**: the mapping heuristic (exact match, stem match, no-match, dedup),
  payload extraction/malformed-payload handling, worker handler/dispatcher wiring
  for the two new event types.
- **Integration** (real Postgres/Redis/Kafka): repository CRUD and upsert
  idempotency, **both correlation orderings** explicitly tested
  (`test_pr_changed_before_ci_run_still_computes_impact` and
  `test_ci_run_before_pr_changed_still_computes_impact`) — this is the actual
  claim the design notes make, verified, not asserted; full `/ingest/test-results`
  API flow (202/404/403); full `GET .../test-impact` API flow (200/404).

## Observability

- Structured logs: `worker.test_intelligence.pr_changed_processed`,
  `worker.test_intelligence.ci_run_processed`. Same deferral as 9.0/9.1 on
  spans/metrics — revisited once enough consumers exist to fix span boundaries
  deliberately rather than piecemeal.

## Security considerations

- `write:test-results` is a distinct scope from all `read:*` scopes — a CI job's
  token cannot read analysis results, and a read-scoped user token cannot post
  fake test results. Verified by the 403 test using a `read:pr-analysis` token
  against the ingest endpoint.
- **Fixed same-day**: the ingest endpoint now *requires* the bearer token to carry
  an `installation_id` claim matching the installation resolved from
  `repository` — a token missing the claim, or scoped to a different
  installation, is rejected with `403 SIBYL_INSTALLATION_MISMATCH`. Without this,
  any token with `write:test-results` (regardless of which org it was meant for)
  could post fabricated test results against *any* organization known to the
  system, since `repository` is caller-supplied. Tested explicitly: missing
  claim, mismatched claim, and matching claim all have dedicated tests. Token
  *issuance* that actually sets this claim correctly still doesn't exist (see the
  Stage 9.0 addendum) — this fix closes the verification side, not the
  provisioning side, of the gap.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 84 tests passing, 92% overall coverage.
- [x] `test_intelligence` Alembic branch generated and applied against a real
      Postgres, verified via `\dt` (7 tables).
- [x] Stage 4 and Stage 5 addenda logged for the `/ingest/test-results` gap.
- [x] `write:test-results` tokens are installation-bound (fixed same-day, see
      Security considerations); token *issuance* remains deferred (Stage 9.0
      addendum), tracked separately, not conflated with this fix.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: discovered and fixed the GitHub-webhook-has-no-per-test-data gap (new `/ingest/test-results` endpoint, Stage 4/5 addenda); built `test_intelligence` domain/persistence/service/API; bidirectional correlation replacing the diagram's buffer-and-poll sketch; restructured worker to run multiple concurrent consumer groups; fixed an `Installation` lookup bug (assumed uniqueness that test data violated). |
| 2026-07-02 | Closed the cross-installation injection gap flagged the same day: `TokenPayload`/`create_access_token` gained an `installation_id` claim; `/ingest/test-results` now requires it to match the resolved installation. Token issuance that sets this claim correctly remains deferred (Stage 9.0 addendum). |
