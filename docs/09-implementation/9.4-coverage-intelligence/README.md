# Sub-stage 9.4 — Coverage Intelligence

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation), 9.2 (Test Impact Analysis)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Serves Persona #2 from `docs/01-problem-discovery/README.md` (platform/CI-owning
engineer), grouped with CI/CD Optimization as secondary/indirect evidence per
`docs/02-product-discovery/README.md` (Phase 2, not MVP). Stage 9's own
roadmap description is the sharpest framing available: "builds on the
test-impact data model to reason about coverage gaps meaningfully rather than
raw percentages." A raw coverage percentage on a file nobody touches is
noise; a low-or-unknown coverage percentage on a file that keeps changing is
a real, actionable signal.

## Scope

**In scope:**
- A `file_coverage_signal` read-model in Test Intelligence — a **snapshot**
  (not rolling-window) per-file coverage percentage, overwritten on each new
  report for that file.
- `POST /ingest/coverage-report` (Ingestion, Stage 5 addendum), scoped to a
  new `write:coverage-reports` scope — same pattern as 9.2's
  `/ingest/test-results`, including the installation-binding check **built
  in from day one** (9.2's version of this check was initially missing and
  fixed same-day; no reason to reintroduce that gap on a second endpoint now
  that the fix is an established pattern).
- `GET /repositories/{owner}/{repo}/coverage/gaps` (Stage 5 addendum), reusing
  `read:test-intelligence` — ranks files that appeared in the repository's
  most recent 20 PRs' changed-file lists (reusing `pr_changed_files_projection`,
  already owned by this context since 9.1/9.2) by coverage-gap severity:
  files with **no coverage data at all** rank first (most severe — an
  unknown gap on actively-changed code), then known percentages ascending.
- **A real architectural decision made and logged before writing code**:
  Coverage Intelligence joins Test Intelligence as a **fourth** capability
  (impact, flakiness, duration, now coverage). The ADR-0002 addendum from 9.5
  explicitly flagged a fourth capability as "the point to revisit whether
  this context has grown too coarse" — revisited here, explicitly, not just
  defaulted into. See Design notes.

**Explicitly out of scope (this pass):**
- Change-frequency as its own tracked metric — deliberately reused
  `pr_changed_files_projection`'s existing PR history instead of building a
  parallel "how often does this file change" subsystem. If PR history proves
  too coarse a proxy for "actively changing," that's a real design
  conversation for later, not solved speculatively now.
- Any specific coverage-report file format (coverage.xml, lcov, `.coverage`
  sqlite) — the ingest endpoint's contract is a minimal normalized JSON
  shape (`filePath`/`linesCovered`/`linesTotal`), the same "CI job reports a
  normalized shape, not a raw artifact" principle already used for
  `/ingest/test-results`. Parsing real coverage-tool output formats into that
  shape is the CI job's responsibility, not this endpoint's.
- Branch/condition coverage, only line coverage — no persona evidence asks
  for more granularity than line coverage yet.
- A Kafka event downstream of `file_coverage_signal` being updated — no
  consumer exists (same reasoning as 9.5's `test_duration_signal`).

## Contracts consumed / amended

- Architecture: `docs/03-architecture/adr/0002-bounded-context-map.md` —
  addendum assigning this capability to Test Intelligence, and setting an
  explicit "a fifth capability requires a mandatory context-split
  evaluation" threshold; cross-referenced in `docs/03-architecture/README.md`.
- Data model: `docs/04-database/README.md` (`test_intelligence.file_coverage_signal`,
  new `ingestion.coverage-report-received` topic) — addendum.
- API surface: `docs/05-api-design/openapi.yaml` — new `coverage-intelligence`
  tag, `POST /ingest/coverage-report`, `GET .../coverage/gaps`,
  `write:coverage-reports` scope; addendum in `docs/05-api-design/README.md`
  (including an update to the RBAC scope catalog table, which had drifted
  out of sync with the 9.2/9.5 addenda already logged in the decisions log
  but never reflected in the table itself — fixed while touching this area).
- Runtime flow: `docs/06-sequence-diagrams/README.md` §9 — new diagram,
  deliberately simpler than §1/§4 (no LLM, no correlation, no downstream
  event) and explicit about why it doesn't need either.

## Design notes specific to this sub-stage

- **The "fourth capability" threshold, revisited honestly, not rubber-stamped.**
  All four of Test Intelligence's capabilities (impact, flakiness, duration,
  coverage) answer different questions about the same underlying fact ("a
  test ran, what does that tell us") — none has independent business rules
  or vocabulary, none needs a different persistence or event-consumption
  shape. This is different in kind from Root Cause Analysis, which earned
  its own context because "hypothesis" is a real, distinct domain concept.
  The ADR-0002 addendum sets a concrete rule for next time: a **fifth**
  capability triggers a mandatory split evaluation, not another "revisit
  later" — a deliberately firmer line than the vague one set at the third.
- **Snapshot, not rolling window — a genuinely different signal shape than
  flakiness/duration.** Coverage percentage is a fact about a specific
  commit; smoothing it across history the way flakiness/duration windows do
  would answer a question nobody asked ("what's the median coverage over the
  last 20 reports" is not a meaningful metric the way "median duration" or
  "flakiness rate" are). Each report simply overwrites the previous
  `(repository, file_path)` row.
- **Reusing `pr_changed_files_projection` instead of a new frequency
  tracker.** A coverage gap is only interesting in the context of actively-changed
  code — building a separate "change frequency" subsystem would duplicate
  data this context already owns from 9.1/9.2. This is the same
  "don't build a fact table you already have a fact table for" reasoning
  used throughout this project (e.g., not persisting full diff content).
- **Installation-binding built in from day one, not deferred.** 9.2's
  `/ingest/test-results` shipped without this check, and it was found and
  fixed as a same-day follow-up once the gap was identified. That fix
  established a known-good pattern; `/ingest/coverage-report` uses it
  immediately rather than repeating the same discovery-then-fix cycle on a
  second write-capable, caller-supplied-repository endpoint.
- **Ranking null-coverage files first is a deliberate product decision, not
  an implementation accident.** A file with 40% coverage that changes
  constantly is a known, quantified risk; a file with *no coverage data at
  all* that changes constantly is a bigger unknown — the ranking reflects
  that severity ordering explicitly (verified by a dedicated repository test),
  not just "whatever SQL sort was convenient."
- **Coverage-tool tracing artifact (not a real gap):** `coverage_api.py`
  reports 85% via the coverage tool, missing exactly the success-path block
  — the identical pattern already present (and accepted) in the existing
  `test_results_api.py` (86%, same missing-block shape) and previously
  diagnosed in the 9.9 sub-stage doc for `root_cause_analysis/api.py`. Not
  re-diagnosed with a debug print again here since the pattern is now known
  and consistent across every `/ingest/*` endpoint using the same
  `async with session_factory() as session, session.begin():` shape.

## Test plan

Per `docs/08-testing-strategy/README.md`: 186 tests total (up from 163 at
9.5), all passing; 93% overall coverage, all new modules at 100% except
`application.py` (99%, one structurally-unreachable defensive guard, same
shape as 9.5's) and `coverage_api.py` (85%, the known coverage-tool artifact
above).

- **Unit**: `compute_coverage_pct` (partial, full, zero, and the
  divide-by-zero guard for a file with 0 total lines).
- **Integration** (real Postgres): repository CRUD/upsert (confirms
  overwrite-not-window semantics); `get_recently_changed_files` (dedup
  across multiple PRs, respects `pr_window`); `list_coverage_gaps`
  explicitly tested for **no-signal files ranking first**, **known
  percentages ascending after that**, **respecting `limit`**, and the
  **empty-repository case**. Full ingest API flow (202/403 missing
  claim/403 mismatched installation/404 unknown org/403 missing scope,
  mirroring 9.2's test suite exactly). Full read API flow (200 with correct
  ranking, empty list, `limit` query param, 403 without scope). Worker
  handler wiring exercised end-to-end.
- **Found and fixed a real, pre-existing test-isolation bug while adding
  these tests, unrelated to Coverage Intelligence's own logic**:
  `tests/integration/test_relay.py` asserted `published_count == 1` against
  `OutboxRepository.fetch_unpublished`, which scans the *entire*
  `ingestion.outbox_event` table with no scoping. This was already fragile —
  any other test that commits an ingestion outbox row without ever relaying
  it (which `test_test_results_ingest_api.py` already did) leaves a
  permanent unpublished row in the shared session-scoped test database. It
  only became visible once a new test file (`test_coverage_ingest_api.py`)
  happened to sort alphabetically before `test_relay.py`, changing which
  leftover rows existed by the time that assertion ran. Fixed the assertion
  to `>= 1` (robust to other tests' outbox state, which was never something
  this test should have depended on) rather than working around the ordering
  by renaming files.

## Observability

- Structured logs: `worker.test_intelligence.coverage_report_processed`. Same
  deferral as every prior sub-stage on dedicated spans/metrics.

## Security considerations

- `POST /ingest/coverage-report` requires `write:coverage-reports` (a new,
  narrow scope — not reusing `write:test-results`, since a token meant only
  to report coverage shouldn't also be able to report fabricated test
  results, per the existing least-privilege principle) and the
  installation-binding check from the first version shipped, not as a
  follow-up.
- `GET .../coverage/gaps` reuses `read:test-intelligence` — read-only
  analytics over data already governed by that scope; no new read-side
  authorization surface needed.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 186 tests passing, 93% overall coverage.
- [x] `test_intelligence` Alembic branch extended with a clean, isolated
      incremental migration (only the one new table), applied against a real
      Postgres, verified via `\dt` (9 tables) and `alembic heads` (all 5
      branches still resolve to a single head each).
- [x] ADR-0002 and Stage 4/5/6 addenda logged for the bounded-context
      decision, the new table/topic, the new endpoints, and the runtime flow.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: `file_coverage_signal` snapshot signal, `POST /ingest/coverage-report` (with installation-binding built in from day one), `GET .../coverage/gaps` ranking (no-signal files first). Made and logged the bounded-context decision (Coverage Intelligence joins Test Intelligence as its fourth capability) before writing code, including a concrete threshold for when a fifth capability would force a real context-split evaluation. Found and fixed a pre-existing test-isolation bug in `test_relay.py`, exposed (not caused) by this sub-stage's new tests. |
