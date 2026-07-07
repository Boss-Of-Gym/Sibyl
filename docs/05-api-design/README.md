# Stage 5 — API Design

**Status:** `APPROVED` (2026-07-02)
**Leads:** System Analyst, Staff Backend Engineer
**Reviewers:** Principal Software Engineer, UX Engineer
**Entry criteria:** Stage 4 (Database) `APPROVED`.

## Goal

Define the platform's external contract before any endpoint is implemented. The API
is the thing external integrators, the future web UI, and webhook consumers all
depend on — it changes shape far more expensively after Stage 9 starts than before.

## Key questions / activities

- **REST/OpenAPI 3.1 spec** for all synchronous operations, organized by bounded
  context from Stage 3.
- **Versioning strategy**: URL/header-based, deprecation policy, breaking-change
  process — this project builds "API Evolution Tracking" as a product feature, so its
  own API discipline should be exemplary and ideally dogfood-able.
- **AuthN/AuthZ model**: OAuth2 + JWT, scopes mapped to each of the 17 capabilities
  (e.g. read:pr-analysis, admin:integrations) — least-privilege by construction, not
  a single all-or-nothing API key.
- **Webhook/event subscription API**: how external systems (or the platform's own
  future UI) subscribe to outbound events like "release-risk-score-computed" or
  "flaky-test-detected" — contract, delivery guarantees, retry/backoff behavior.
- **Error model**: a single consistent error shape (e.g. RFC 7807 problem+json) across
  every endpoint — no per-endpoint bespoke error formats.
- **Pagination, filtering, sorting conventions**: decided once, applied everywhere.
- **Rate limiting**: policy and where it's enforced (gateway vs. application layer),
  consistent with the Redis usage catalog from Stage 4.

## Deliverables

- Versioned OpenAPI 3.1 specification.
- API style guide (naming, pagination, error shape, versioning policy).
- RBAC scope catalog mapped to capabilities.
- Webhook/event contract documentation.

## Findings (final — approved 2026-07-02)

### OpenAPI spec

[`openapi.yaml`](openapi.yaml) — OpenAPI 3.1, validated structurally with
`openapi-spec-validator` (passes with no errors; Spectral-style style-linting is a
Stage 7 CI concern once the pipeline exists, referenced here for continuity).

**Design principle:** the API exposes only what Sibyl *adds* — PR Analysis, Test
Impact Analysis, Flaky Detection signals, Root Cause Analysis hypotheses. It does
not re-expose GitHub's own data (PR metadata, diffs, commit info) — clients already
have GitHub for that. Every read endpoint traces to a Stage 2 confirmed MVP
capability; there is no endpoint for a Phase 2/3 capability, and no generic
"list all analyses" history/feed endpoint — Stage 2 explicitly scoped MVP to
single-artifact questions ("this PR," "this test," "this failure"), not
aggregate/historical views (that's the deferred-dashboard territory from ADR
discussions in Stage 2/3).

**Resource addressing:** `owner/repo` (GitHub's own convention), not internal
`installation_id` — the public contract never leaks the Stage 4 internal scoping
key; it's resolved server-side from the authenticated caller's accessible
installations.

### Versioning strategy

**URL-based versioning** (`/v1/...`), not header-based. Reasoning: URL versioning
is trivially discoverable and testable (curl, browser, API docs) without needing
custom header knowledge — a meaningfully lower barrier for external
integrators/CLI users than the marginal "elegance" of header versioning.

**Security-specific reasoning (the deciding factor):** URL versioning allows
per-version isolation and patching at the infrastructure layer — an ingress/WAF can
route or cut off traffic to a specific version without code changes, which header
-based versioning makes much harder (requires deep header inspection at every
infra layer most WAFs/CDNs support less well than path routing). URL versioning
also means the version is captured by default in access logs and SIEM tooling,
which matters directly for incident response — header-based versions require
deliberate extra log enrichment or the version is invisible during an investigation.
The common argument that hiding the version in a header is "more secure" is
security-through-obscurity: a real attacker reads the API docs and knows the
version regardless. Header versioning's one genuine advantage — a single canonical
route reduces the risk of forgetting to wire auth middleware onto a new versioned
route — is fully mitigated by applying middleware/dependencies at the
version-prefixed router level (FastAPI `APIRouter`), not per-endpoint. Since
Sibyl's own roadmap includes API Evolution Tracking (Phase 2), the plan is to
eventually dogfood that capability against Sibyl's own spec version history — noted
here, not built now, same pattern as the Stage 4 dogfooding note.

**Breaking-change policy:** any breaking change ships as a new major version path
(`/v2/...`); the previous version remains available for a minimum deprecation
window, advertised via `Deprecation` and `Sunset` response headers (RFC 8594) on
the old version's endpoints — not silently removed.

### RBAC scope catalog

Scoped to the 4 MVP capabilities only at Stage 5 — no scopes were pre-created
for unbuilt Phase 2/3 capabilities (same discipline as not pre-writing their
implementation docs). *(Table kept in sync with Stage 9 addenda below — a new
read-only Phase 2 endpoint reuses an existing capability's scope only when it
lives inside that same bounded context (9.5/9.4 both joined Test
Intelligence, so both reuse `read:test-intelligence`); a new bounded context
gets its own new scope, since reusing another context's scope would leak
access across an actual authorization boundary — Dependency Analysis (9.6)
is the first Phase 2 example of this.)*

| Scope | Grants |
|---|---|
| `read:pr-analysis` | `GET .../pr-analysis` |
| `read:test-intelligence` | `GET .../test-impact`, `GET .../stability`, `GET .../ci-cd/slow-tests` *(9.5)*, `GET .../coverage/gaps` *(9.4)* |
| `read:root-cause` | `GET .../root-cause` |
| `read:dependency-analysis` *(9.6)* | `GET .../dependencies`, `GET .../dependencies/changes` *(9.8)* |
| `read:regression-prediction` *(9.10)* | `GET .../regression-prediction` |
| `admin:installations` | `GET /installations`, `GET /installations/{id}/repositories` |
| `write:test-results` *(9.2)* | `POST /ingest/test-results` |
| `write:coverage-reports` *(9.4)* | `POST /ingest/coverage-report` |
| `write:dependency-manifests` *(9.6)* | `POST /ingest/dependency-manifest` |

**AuthN:** GitHub OAuth login issues a Sibyl-scoped JWT (`bearerAuth` in the spec),
scoped to the installations the authenticated GitHub user actually has access to
(verified against GitHub's own permission model, not re-implemented). The
`/webhooks/github` endpoint is the one exception — authenticated via HMAC signature
verification against the GitHub App's webhook secret, not a bearer token, since the
caller there is GitHub itself, not an end user.

### Webhook/outbound-event contract — deliberately narrow for MVP

The only outbound integration in MVP is **Sibyl → GitHub Checks API** (Sibyl acting
as a client, creating/updating check runs) — this is not a public subscription API,
it's an internal adapter (Ingestion/PR-Analysis/Root-Cause-Analysis → GitHub
Checks). **A generic "subscribe to Sibyl events" API for third-party consumers is
explicitly out of scope for MVP** — no persona or MVP capability needs it yet, and
building one now would be speculative infrastructure for consumers that don't
exist. This is revisited in Phase 2+ once a real external-consumer need appears
(e.g., a ChatOps integration).

### Error model

RFC 7807 (`application/problem+json`) everywhere, extended with a Sibyl-specific
`code` field (e.g. `SIBYL_ANALYSIS_NOT_READY`) for programmatic handling beyond the
HTTP status alone. No endpoint uses a bespoke error shape.

### Pagination

Cursor-based (`?cursor=...&limit=...`), not offset-based — offset pagination drifts
under concurrent inserts (new installations/repositories arriving), which cursor
pagination avoids. Applied to the only two list endpoints in MVP
(`/installations`, `/installations/{id}/repositories`); the analysis endpoints are
all single-resource lookups, not lists, consistent with the single-artifact scope
decided in Stage 2.

### Rate limiting

**New Redis usage, extending the Stage 4 catalog:** inbound API rate limiting per
JWT (token-bucket, e.g. 60 requests/min for read endpoints), enforced at the
FastAPI application layer (no separate gateway in MVP, consistent with ADR-0001's
modular-monolith reasoning — a dedicated API gateway is unearned infrastructure at
this scale). This is a 5th Redis use case beyond Stage 4's original 4; recorded
here and cross-referenced back into `docs/04-database/README.md`'s catalog for a
single source of truth.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| URL-based versioning (`/v1/...`) | Header/media-type-based versioning | Security reasoning: enables per-version infra-level isolation/patching and default log/SIEM visibility, both meaningfully harder with header versioning; the "hidden version is safer" argument is security-through-obscurity | System Analyst / user |
| No public webhook-subscription API in MVP; the only outbound integration (Sibyl → GitHub Checks) is an internal adapter, not a public contract | Building a general subscription API now | No persona or MVP capability needs external subscribers yet; would be speculative infrastructure | System Analyst / user |
| API exposes only Sibyl-derived data, never re-exposes GitHub's own PR/diff/commit data | Mirroring relevant GitHub resource shapes for convenience | Clients already have GitHub for that; duplicating it adds a second copy to keep consistent for no benefit — same reasoning as the Stage 4 no-full-diff-storage decision | Staff Backend Engineer |
| Cursor-based pagination for the 2 list endpoints | Offset-based pagination | Offset pagination drifts under concurrent inserts; no list endpoint is large enough in MVP to need more than a simple cursor | Staff Backend Engineer |
| RFC 7807 (`application/problem+json`) with an added `code` field, used on every error response | Bespoke per-endpoint error shapes | Consistency the checklist explicitly requires; the `code` field adds programmatic handling RFC 7807 alone doesn't provide | System Analyst |
| *(Addendum, Stage 9.2)* Added `POST /ingest/test-results` and a new `write:test-results` scope | Trying to extract per-test results from GitHub's native `check_suite`/`workflow_run` webhook payload | GitHub's webhook only carries a suite-level conclusion, never per-test results — the Stage 4 `test_case_result` schema (test_identifier, status, duration_ms) has no possible data source without the CI job itself reporting results. This is the same pattern real CI-observability products (BuildPulse, Datadog CI Visibility) use: a dedicated reporting step in the CI job, not a passive webhook. | System Analyst / user |
| *(Addendum, Stage 9.3)* `GET .../tests/{testIdentifier}/stability` matches `testIdentifier` as a greedy path segment (FastAPI/Starlette `:path` converter), not a single path component | Percent-encoding `/` in the client (`%2F`) | This gap was only caught while writing the 9.3 implementation, not during the original Stage 5 design: `testIdentifier` values are pytest node IDs (`tests/test_x.py::test_x`), which always contain literal `/`. A plain `{testIdentifier}` path param uses Starlette's default `str` converter, which stops at `/` — the route silently never matches a real identifier (404 on every real request, not just missing ones). Requiring clients to percent-encode was rejected: it pushes a server-routing detail onto every caller and most HTTP clients don't encode path segments by default, so it fails the same way in practice. | Staff Backend Engineer |
| *(Addendum, Stage 9.5)* Added `GET .../ci-cd/slow-tests`, scoped to the existing `read:test-intelligence` (no new scope), with `limit`-only pagination instead of the cursor pattern used by the other 2 list endpoints | Cursor pagination, for consistency with the existing 2 list endpoints | This endpoint returns a bounded top-N ranking (the N slowest tests), not an arbitrarily-growing collection — a cursor has nothing left to page through once the ranking is exhausted, so applying the same pattern here would be consistency for its own sake, not because the access pattern actually needs it | Staff Backend Engineer |
| *(Addendum, Stage 9.4)* Added `POST /ingest/coverage-report` + `write:coverage-reports` scope (mirroring 9.2's `write:test-results`, with the installation-binding check built in from day one, not deferred); added `GET .../coverage/gaps`, reusing `read:test-intelligence` | Folding coverage into the existing `/ingest/test-results` payload; deferring the installation-binding check the way 9.2 initially did | A CI job that only reports coverage shouldn't have to fabricate a per-test breakdown to satisfy one combined schema — two independently-versionable contracts. The installation-binding gap in `write:test-results` was a real, if quickly-fixed, security lapse (see the 9.2/9.0 addenda) — no reason to reintroduce the same gap on a second write-capable endpoint now that the fix pattern is established. | System Analyst / Senior Security Engineer |
| *(Addendum, Stage 9.6)* Added `POST /ingest/dependency-manifest` + `write:dependency-manifests`, and `GET .../dependencies` + a **new** `read:dependency-analysis` scope (not a reuse of `read:test-intelligence`) | Reusing `read:test-intelligence` for the new read endpoint, matching the 9.4/9.5 pattern | Dependency Analysis is a new bounded context (Stage 9.6 ADR-0002 addendum), not a Test Intelligence capability like 9.4/9.5 were — reusing `read:test-intelligence` here would let any test-intelligence-scoped caller read a completely unrelated context's data, an actual authorization-boundary leak, not a convenience | System Analyst / Senior Security Engineer |
| *(Addendum, Stage 9.8)* Added `GET .../dependencies/changes`, reusing `read:dependency-analysis` (no new scope) — the opposite pattern-application from 9.6's own addendum, correctly, because this joined the *same* context 9.6 already scoped | Minting a new `read:api-evolution` scope | This capability lives inside `dependency_analysis` (Stage 9.8 ADR-0002 addendum), not a new context like 9.6 was relative to Test Intelligence — reuse is correct here for the same reason it was correct for 9.4/9.5 inside Test Intelligence: same bounded context, same authorization boundary | System Analyst / Senior Security Engineer |

## Architecture Review checklist (exit criteria)

- [x] OpenAPI spec exists, is versioned, and passes lint (e.g. Spectral) with no
      errors. *(Validated structurally with `openapi-spec-validator`; full
      Spectral style-linting wired into CI at Stage 7.)*
- [x] Every endpoint traces to a Stage 2 user journey — no speculative endpoints.
- [x] Auth scopes are least-privilege and mapped explicitly to capabilities, not a
      single global API key/scope.
- [x] A breaking-change/versioning policy is written down and specific (not "we'll be
      careful").
- [x] Error response shape is single and consistent across the whole spec.
- [x] Principal SWE and UX Engineer have reviewed for consistency and for actual
      alignment with the Stage 2 interaction model.
- [x] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Previous stage: `docs/04-database/README.md`
- Next stage: `docs/06-sequence-diagrams/README.md`
- `PROGRESS.md` entries tagged Stage 5
