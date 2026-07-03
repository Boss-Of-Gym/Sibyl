# Sub-stage 9.8 — API Evolution Tracking

**Status:** `APPROVED` (2026-07-02)
**Depends on:** 9.0 (Platform Foundation), 9.6 (Dependency Analysis)
**Owner roles:** Senior Python Developer, Senior SDET
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Identical evidence tier to Dependency Analysis (9.6): no Stage 1 persona,
"market/competitive only" per `docs/02-product-discovery/README.md` — the
weakest tier, same as 9.6, weaker than 9.4/9.5's secondary/indirect tier.
Stage 9's own roadmap description is the operative scope statement: "needs
dependency/manifest awareness (9.6) plus OpenAPI-diffing to detect breaking
changes across services." That description was read narrowly and
deliberately — see Scope and Design notes — rather than taken as a mandate
to build a full OpenAPI-spec-diffing engine for a capability with zero
persona evidence.

## Scope

**In scope:**
- **Dependency-version breaking-change detection**, computed at read time
  from data 9.6 already stores: given the two most recent
  `dependency_manifest_snapshot` rows for a `(repository, ecosystem)`, diff
  the package lists by name and classify each change — added (non-breaking),
  removed (breaking), or version-changed (breaking if the leading major
  version number differs, non-breaking otherwise, unknown if a version
  string can't be parsed).
- `GET /repositories/{owner}/{repo}/dependencies/changes?ecosystem=...`
  (Stage 5 addendum), reusing the existing `read:dependency-analysis` scope
  — no new scope needed, because this joined the same bounded context.
- **A real architectural decision, using the exact evaluation framework
  established for this purpose, run in the opposite direction from 9.6's own
  precedent**: API Evolution Tracking is a **second capability inside
  Dependency Analysis**, not a new context. See Design notes.
- **A real scope-interpretation decision, presented to and confirmed by the
  user before implementation**: "API Evolution Tracking" here means
  dependency-version classification, not literal OpenAPI-spec diffing.

**Explicitly out of scope (this pass):**
- **Literal OpenAPI-spec diffing** — parsing and comparing a repository's own
  `openapi.yaml`/`swagger.json` across commits to detect endpoint/schema-level
  breaking changes. This is a genuinely different, larger capability: it
  needs a new ingestion source (a repo's own spec, not its dependency
  manifest — a different fact, which likely *would* argue for a new bounded
  context if built), a real OpenAPI parser, and per-field breaking-change
  rules (removed endpoint, removed required-response-field, narrowed
  parameter type, etc.). Building that for a zero-evidence capability was
  judged disproportionate; this remains a real, undecided future option, not
  assumed as part of "API Evolution Tracking" by default just because the
  name suggests it.
- Persisting diff results — a diff is fully re-derivable from the two
  snapshots that already exist, so storing one would be speculative
  infrastructure (no consumer needs a historical record of past diffs, only
  the current comparison).
- Arbitrary commit-pair selection — only "the two most recently reported
  snapshots" is supported; explicit `fromCommit`/`toCommit` selection can be
  added later if a real use case asks for it.
- Cross-ecosystem or cross-repository comparison — one `(repository,
  ecosystem)` pair per request, matching the shape 9.6 already established.

## Contracts consumed / amended

- Architecture: `docs/03-architecture/adr/0002-bounded-context-map.md` —
  addendum: joins `dependency_analysis` as a second capability; cross-referenced
  in `docs/03-architecture/README.md`.
- Data model: `docs/04-database/README.md` — addendum noting **no new table**
  was needed (a genuine, cheap extension of 9.6's existing schema).
- API surface: `docs/05-api-design/openapi.yaml` — new
  `GET .../dependencies/changes` operation, `DependencyChange`/`DependencyChanges`
  schemas, reusing the existing `dependency-analysis` tag and
  `read:dependency-analysis` scope; addendum in `docs/05-api-design/README.md`
  (RBAC catalog grants list extended, not a new row).
- Runtime flow: `docs/06-sequence-diagrams/README.md` §11 — new diagram, the
  simplest yet (no Kafka involvement at all — a pure read-time computation
  over data §10 already wrote).

## Design notes specific to this sub-stage

- **Running the ubiquitous-language evaluation in the joining direction —
  the mirror image of 9.6's own decision.** 9.6 correctly became a new
  context because a dependency manifest shares no domain language with
  test-run history. Here the comparison is different: does "classify a
  version change as breaking" share domain language with "store a
  dependency manifest snapshot"? Yes — it's the same fact
  (`dependency_manifest_snapshot`) asked a new question, structurally
  identical to how Test Impact Analysis/Flaky Detection/CI/CD
  Optimization/Coverage Intelligence each ask a different question about the
  same test-run fact inside Test Intelligence. The framework isn't
  "new capabilities always get new contexts" or "always join" — it's "does
  this share a real domain fact," applied honestly each time, which is why
  it correctly produced opposite answers for 9.6 and 9.8.
- **The scope-interpretation decision was presented to the user, not
  assumed.** "OpenAPI-diffing" in the roadmap text could honestly be read
  literally. Given zero persona evidence either way, the choice was: (a)
  narrow interpretation, reusing 9.6's already-stored history with a cheap
  semver heuristic, or (b) literal interpretation, building an entirely new
  ingestion pipeline and spec-diff engine. The user confirmed (a) explicitly
  before implementation began.
- **No new table is itself evidence the "join" decision was right.** A
  capability that can be fully implemented by reading two existing rows and
  computing a pure function over them is about as clear a signal as exists
  that it belongs in the context already holding that data — the cheapest
  possible extension, not a coincidence.
- **Semver classification is a heuristic, not a real semver-spec parser.**
  `_leading_major` extracts the first integer from a version string (with an
  optional leading `v`) and nothing else — it doesn't validate the rest of
  the string, doesn't handle pre-release/build-metadata suffixes specially,
  and isn't guaranteed correct for every ecosystem's actual versioning
  convention (Go modules' `v2+` path-based major versioning, Python's
  occasional non-PEP-440 strings, etc.). This is an honest, documented
  simplification appropriate to a zero-evidence capability — a full
  per-ecosystem version-spec parser would be real effort spent on a feature
  nobody has asked for yet.

## Test plan

Per `docs/08-testing-strategy/README.md`: 217 tests total (up from 201 at
9.6), all passing (re-run twice); 93% overall coverage, `dependency_analysis`
at a full 100% (including `api.py` — no coverage-tracing artifact this time,
since this endpoint has no `session.begin()` write-transaction shape, unlike
every `/ingest/*` endpoint).

- **Unit**: `classify_version_change` (major/minor/patch bumps, unparseable
  versions on either side, `v`-prefixed versions) and `diff_packages`
  (added/removed/version-changed detection, unchanged packages produce no
  entry, results sorted by name) — all pure, no I/O.
- **Integration** (real Postgres): `get_recent_snapshots` (most-recent-first
  ordering, scoped per ecosystem, empty when nothing exists). Full API flow:
  200 with a correctly classified diff between two real snapshots, 404 when
  fewer than two snapshots exist for the requested ecosystem, 403 without
  the scope (using a `read:test-intelligence` token specifically, same
  "wrong specific scope, not just any wrong scope" pattern as 9.6).

## Observability

- No new structured log events — this is a pure read endpoint with no
  write/consume path to log against, unlike every prior sub-stage's ingest
  handler.

## Security considerations

- Reuses `read:dependency-analysis` rather than minting a new scope —
  correct here because this is the same bounded context 9.6 already scoped,
  the mirror image of why 9.6 correctly minted a *new* scope relative to
  Test Intelligence.
- No new write path, no new caller-supplied-data trust boundary — purely
  derived from data already validated and stored by 9.6's ingest endpoint.

## Definition of Done

- [x] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [x] No comments in the code.
- [x] `ruff check .` and `mypy src tests` (strict) pass with zero issues.
- [x] 217 tests passing, 93% overall coverage.
- [x] No new Alembic migration needed (no new table) — confirmed by design,
      not an oversight.
- [x] ADR-0002 and Stage 4/5/6 addenda logged for the bounded-context
      decision, the "no new table" note, the new endpoint, and the runtime
      flow.
- [x] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated per step, in Russian.
- [x] `PROGRESS.md` updated.
- [x] No secret committed.

## Changelog

| Date | Change |
|---|---|
| 2026-07-02 | Initial implementation: `diff_packages`/`classify_version_change` pure functions, `get_recent_snapshots` repository method, `GET .../dependencies/changes` endpoint. Ran the ubiquitous-language evaluation in the joining direction (API Evolution Tracking joins Dependency Analysis), the mirror image of 9.6's own new-context decision. Confirmed the scope interpretation (dependency-version semver classification, not literal OpenAPI-spec diffing) with the user before implementation. |
