# Sub-stage 9.6 — Dependency Analysis

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

**Honestly, this is the weakest-evidenced capability built so far.** Per
`docs/01-problem-discovery/README.md`, no Stage 1 persona mentions dependency
or manifest analysis at all. Per `docs/02-product-discovery/README.md`,
Dependency Analysis lands in the "market/competitive only" evidence tier —
not even the secondary/indirect tier Coverage Intelligence and CI/CD
Optimization had. Its Phase 2 inclusion rationale, verbatim from Stage 2, is
that it's a "natural extension of Phase 1's data, still plausible even
without direct persona evidence because it reuses Phase 1's signal rather
than inventing new integration surface" — which is itself only partly true
here, since (unlike 9.4/9.5) this sub-stage *does* need a wholly new
ingestion source, not a reuse of existing signal. This was already litigated
and accepted at Stage 2 (the phase grouping was "confirmed as-is" without
changes), so this sub-stage does not re-argue scope — it implements what was
already decided, honestly documenting the evidence tier rather than
overstating it. Its real value today is unlocking 9.8 (API Evolution
Tracking), which explicitly depends on it.

## Scope

**In scope:**
- A `dependency_manifest_snapshot` table storing **history** (a row per
  `(repository, commit_sha, ecosystem)`, never overwritten) — a genuinely
  different persistence shape than every Test Intelligence signal table,
  because 9.8 will need to diff manifests across commits later.
- `POST /ingest/dependency-manifest` (Ingestion, Stage 5 addendum), scoped to
  a new `write:dependency-manifests` scope — same pattern as 9.2/9.4's ingest
  endpoints, installation-binding check built in from day one.
- `GET /repositories/{owner}/{repo}/dependencies` (Stage 5 addendum), scoped
  to a **new** `read:dependency-analysis` scope (not a reuse of
  `read:test-intelligence` — this is a different bounded context, reusing
  another context's scope would be an actual authorization-boundary leak,
  not a convenience). Returns the latest known manifest snapshot per
  ecosystem, no risk scoring or staleness classification.
- **A real architectural decision made and logged before writing code, using
  the exact evaluation framework the Stage 9.4 ADR-0002 addendum set up for
  this purpose**: Dependency Analysis is a **new, sixth bounded context**,
  not a fifth capability inside Test Intelligence. See Design notes.

**Explicitly out of scope (this pass):**
- Parsing any real manifest format (package.json, requirements.txt, go.mod,
  poetry.lock, etc.) — the ingest endpoint takes an already-normalized
  `{name, version, direct}` list; a CI job's own script is responsible for
  producing that shape from whatever real manifest/lockfile format it uses.
  Same "normalized shape, not a raw artifact" principle as `/ingest/test-results`
  and `/ingest/coverage-report`.
- Any risk scoring, staleness classification, or vulnerability data — no
  persona evidence justifies inventing a heuristic here, and doing so would
  be exactly the kind of unevidenced feature-building this project's process
  exists to prevent.
- Diffing manifests across commits — that's 9.8's job; this sub-stage's
  responsibility ends at making the history queryable.
- A downstream Kafka event — no consumer exists yet (same reasoning as
  9.4/9.5's signal tables).

## Contracts consumed / amended

- Architecture: `docs/03-architecture/adr/0002-bounded-context-map.md` —
  addendum adding a new, sixth bounded context (the first genuinely new
  context since the Stage 3 freeze, as opposed to 9.4/9.5's "joins an
  existing context" additions); cross-referenced in
  `docs/03-architecture/README.md`.
- Data model: `docs/04-database/README.md` (new `dependency_analysis` schema,
  `dependency_manifest_snapshot` table, `ingestion.dependency-manifest-received`
  topic) — addendum.
- API surface: `docs/05-api-design/openapi.yaml` — new `dependency-analysis`
  tag, `POST /ingest/dependency-manifest`, `GET .../dependencies`, two new
  scopes (`write:dependency-manifests`, `read:dependency-analysis`); addendum
  in `docs/05-api-design/README.md` (RBAC catalog table updated).
- Runtime flow: `docs/06-sequence-diagrams/README.md` §10 — new diagram, the
  simplest in the document (no LLM, no correlation, no downstream event).

## Design notes specific to this sub-stage

- **Running the Stage 9.4 threshold for real, not just citing it.** The
  Stage 9.4 ADR-0002 addendum explicitly required a mandatory context-split
  evaluation before a fifth Test Intelligence capability, rather than another
  vague "revisit later." Doing that evaluation honestly here: a dependency
  manifest (package name, version, ecosystem, direct/transitive) shares
  **no** ubiquitous language with "a test ran, what does that tell us" — it's
  not a different question about the same fact, it's a different fact
  entirely, closer in kind to PR Analysis's diff metadata than to anything
  Test Intelligence owns. The threshold worked as designed: the same
  evaluation framework that said "yes, join" for 9.4/9.5 says "no, don't"
  here, on its own terms, not by exception.
- **History, not a snapshot-per-current-state signal — a genuinely different
  shape than 9.4/9.5's tables.** `test_stability_signal`/`test_duration_signal`/`file_coverage_signal`
  all answer "what's true right now"; `dependency_manifest_snapshot` answers
  "what was true at this specific commit," because 9.8's whole job (API
  Evolution Tracking) will be comparing manifests *across* commits. This
  persistence-shape difference is itself part of the evidence that this
  doesn't belong in Test Intelligence — none of its four signals need
  history the way this one structurally does.
- **Idempotent per commit, not per repository.** Unlike coverage/duration/flakiness
  (upsert keyed on the "current" dimension, e.g. `(repository, test_identifier)`),
  this upserts on `(repository, commit_sha, ecosystem)` — re-ingesting the
  same commit's report is a no-op update, but a new commit always produces a
  new row. `get_latest_snapshots_by_repository` picks the most recent row per
  distinct ecosystem in Python after a single query, the same "simple query
  plus Python-side grouping over simple over clever SQL" choice already made
  for `list_coverage_gaps` in 9.4.
- **New scopes, not reused ones — an actual security decision, not just
  convention-following.** 9.4/9.5 correctly reused `read:test-intelligence`
  because they're capabilities *inside* that same context; minting a new
  scope there would have been scope proliferation for no reason. Here, reuse
  would be wrong for the opposite reason: `read:dependency-analysis` and
  `write:dependency-manifests` are new because this is a new context — a
  token scoped to read test intelligence data has no legitimate reason to
  read dependency data, and conflating the two scopes would quietly create
  exactly that cross-context access.

## Test plan

Per `docs/08-testing-strategy/README.md`: 201 tests total (up from 186 at
9.4), all passing (re-run twice to confirm stability); 93% overall coverage,
all new modules at 100% except `dependency_api.py` (85%, the same
coverage-tool tracing artifact already documented for every other `/ingest/*`
endpoint — not re-diagnosed again, the pattern is established).

- **Integration** (real Postgres): repository upsert semantics explicitly
  tested for **idempotency within the same commit+ecosystem** (re-ingesting
  updates in place) versus **history preservation across commits** (a new
  commit always creates a new row, proven by asserting both rows still exist
  and the "latest" query returns the newer one); `get_latest_snapshots_by_repository`
  tested for the multi-ecosystem case (a polyglot repo reporting both npm and
  pypi) and the empty-repository case. Full ingest API flow (202/403 missing
  claim/403 mismatched installation/404 unknown org/403 missing scope,
  mirroring 9.2's/9.4's suites exactly). Full read API flow (200 with correct
  shape, empty list, and — deliberately — a 403 test using a
  `read:test-intelligence` token specifically, proving the new scope isn't
  accidentally satisfied by an unrelated context's read scope). Worker
  handler wiring exercised end-to-end.

## Observability

- Structured logs: `worker.dependency_analysis.manifest_processed`. Same
  deferral as every prior sub-stage on dedicated spans/metrics.

## Security considerations

- `POST /ingest/dependency-manifest` requires `write:dependency-manifests`
  (new, narrow scope) and the installation-binding check from day one.
- `GET .../dependencies` requires a **new** `read:dependency-analysis` scope,
  not a reuse of any existing scope — verified with a 403 test using a
  `read:test-intelligence` token specifically (not just "any wrong scope"),
  since the realistic failure mode here is "someone assumed adjacent
  Phase-2-read scopes are interchangeable," not a random unrelated scope.
- No LLM, no user-supplied free text beyond package name/version strings
  (stored, never executed or interpolated into a query — parameterized
  throughout, per the existing ORM usage pattern).

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 201 tests passing, 93% overall coverage.
- [x] New `dependency_analysis` Alembic branch created and applied against a
      real Postgres, verified via `\dt` (1 table) and `alembic heads` (all 6
      branches now resolve to a single head each).
- [x] ADR-0002 and Stage 4/5/6 addenda logged for the new bounded context,
      the new schema/topic, the new endpoints/scopes, and the runtime flow.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: new `dependency_analysis` bounded context (schema, repository, application service, API), `POST /ingest/dependency-manifest`, `GET .../dependencies`. Ran the mandatory context-split evaluation the Stage 9.4 ADR-0002 addendum required, concluding — honestly, on the same framework — that this belongs in a new context, not Test Intelligence's fifth capability. Honestly documented this as the weakest-evidenced capability built to date, without re-litigating Stage 2's already-settled scope decision. |
