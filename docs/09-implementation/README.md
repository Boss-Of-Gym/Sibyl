# Stage 9 — Implementation

**Status:** `IN_PROGRESS` — 11/18 sub-stages `APPROVED` (all 4 MVP capabilities
plus Platform Foundation, and all 6 Phase 2 capabilities — see the roadmap
table below; last synced 2026-07-07)
**Leads:** Senior Python Developer, Senior AI Engineer, Senior SDET (per sub-stage)
**Reviewers:** Principal Software Engineer, Senior Security Engineer (per sub-stage)
**Entry criteria:** Stage 8 (Testing Strategy) `APPROVED`.

## Goal

Build the platform, foundation first, then capability by capability — strictly inside
the architecture (Stage 3), data model (Stage 4), API contract (Stage 5), runtime
flows (Stage 6), infrastructure (Stage 7), and test strategy (Stage 8) already frozen.
Sub-stages do not re-litigate platform architecture; if a sub-stage discovers the
architecture doesn't actually fit, that goes back through Stage 3 as a new ADR — it is
not patched around locally.

## How sub-stages work

Unlike Stages 1–8 and 10, **no per-sub-stage `README.md` is pre-written.** Each row
below gets its own `docs/09-implementation/9.NN-<slug>/README.md`, created from
[`docs/00-process/templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md`](../00-process/templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md)
**at the moment that sub-stage's status moves to `IN_PROGRESS`** — not before. This is
deliberate: pre-writing 18 near-empty docs now would read as padding, not rigor, and
would inevitably go stale before that capability's actual design is worked out (which
itself depends on real usage of the earlier capabilities' outputs).

Every sub-stage still runs its own mini design → build → review loop:
1. Confirm the capability's interface against the frozen Stage 5 API and Stage 4 data
   model (extend, don't redesign).
2. Confirm its runtime flow matches or extends a Stage 6 sequence diagram.
3. Implement against the Stage 8 test strategy and platform-wide Definition of Done.
4. Architecture Review against that sub-stage's own checklist (in its README) plus a
   Senior Security Engineer review before merge.

## Sub-stage roadmap

IDs reflect **technical dependency order only** — they are a catalog, not a build
schedule. **Build order** additionally follows the Stage 2 (Product Discovery)
priority: every MVP-tagged sub-stage is built, in dependency order, before any
non-MVP sub-stage — regardless of ID number. Concretely: **9.0 → 9.1 → 9.2 → 9.3 →
9.9**, then the remaining Phase 2 sub-stages, then Phase 3. IDs are not renumbered to
match this, to avoid churning dependency references every time Stage 2 priority is
revisited — the Priority column below is the actual source of build-order truth.

| ID | Capability | Depends on | Priority (Stage 2) | Why here in the sequence | Status |
|---|---|---|---|---|---|
| 9.0 | [Platform Foundation](9.0-platform-foundation/README.md) | Stages 3–8 | MVP | Auth, event backbone, ingestion-adapter framework, observability wiring, CI/CD skeleton — every capability below needs this to exist first. | `APPROVED` |
| 9.1 | [PR Analysis](9.1-pr-analysis/README.md) | 9.0 | **MVP** | Needs only GitHub/GitLab adapters — lowest integration cost, highest immediately-demonstrable value. | `APPROVED` |
| 9.2 | [Test Impact Analysis](9.2-test-impact-analysis/README.md) | 9.0, 9.1 | **MVP** (infra for 9.9, not persona-evidenced itself) | Needs PR diff data (9.1) plus CI/Pytest signal — now via a dedicated `/ingest/test-results` endpoint, see sub-stage doc. | `APPROVED` |
| 9.3 | [Flaky Detection](9.3-flaky-detection/README.md) | 9.0 | **MVP** | Needs only CI/Pytest/Playwright run history — independent of 9.1/9.2, can build in parallel with them. | `APPROVED` |
| 9.9 | [Root Cause Analysis](9.9-root-cause-analysis/README.md) | 9.0, 9.1, 9.2, 9.3 | **MVP** — build immediately after 9.1–9.3, ahead of 9.4–9.8 despite the higher ID | Correlates PR changes, test impact, and flakiness signal to explain *why* something broke. | `APPROVED` |
| 9.4 | [Coverage Intelligence](9.4-coverage-intelligence/README.md) | 9.0, 9.2 | Phase 2 | Builds on the test-impact data model to reason about coverage gaps meaningfully rather than raw percentages. | `APPROVED` |
| 9.5 | [CI/CD Optimization](9.5-ci-cd-optimization/README.md) | 9.0, 9.3 | Phase 2 | Needs reliable run-history and flakiness signal (9.3) to distinguish "slow" from "flaky" before optimizing pipelines. | `APPROVED` |
| 9.6 | [Dependency Analysis](9.6-dependency-analysis/README.md) | 9.0 | Phase 2 | Needs manifest/lockfile ingestion from the foundation; independent of the PR/test-signal chain. | `APPROVED` |
| 9.7 | [Engineering Metrics](9.7-engineering-metrics/README.md) | 9.0, 9.1, 9.3 | Phase 2 | Aggregates PR-flow and CI-health signal into DORA-style metrics — needs those signals to exist first. Scoped down to a PR-flow + CI-health subset; full DORA remains deferred (no deployment ingestion source). | `APPROVED` |
| 9.8 | [API Evolution Tracking](9.8-api-evolution-tracking/README.md) | 9.0, 9.6 | Phase 2 | Needs dependency/manifest awareness (9.6) plus OpenAPI-diffing to detect breaking changes across services. | `APPROVED` |
| 9.10 | [Regression Prediction](9.10-regression-prediction/README.md) | 9.2, 9.9 | Phase 2 | Needs the correlation model from Root Cause Analysis as its training/heuristic basis. | `APPROVED` |
| 9.11 | Release Risk Analysis | 9.4, 9.7, 9.10 | Phase 3 | Fuses coverage, metrics, and regression-risk signal into a single release-level score. | `NOT_STARTED` |
| 9.12 | Release Advisor | 9.11 | Phase 3 | Turns the risk score into an actual LLM-generated go/no-go narrative and recommendation. | `NOT_STARTED` |
| 9.13 | Incident Analysis | 9.9, 9.11 | Phase 3 | Needs root-cause correlation and release-risk history to connect an incident back to a specific release/change. | `NOT_STARTED` |
| 9.14 | AI Documentation | 9.0, 9.1 | Phase 3 | Generative-only capability once PR/code-change data is reliable; deliberately sequenced after correctness-critical analytical capabilities. | `NOT_STARTED` |
| 9.15 | Test Generation | 9.2, 9.4 | Phase 3 | Needs test-impact and coverage-gap data to target generated tests usefully rather than generically. | `NOT_STARTED` |
| 9.16 | Architecture Insights | 9.6, 9.8 | Phase 3 | Needs dependency and API-surface data across services to reason about architecture-level coupling/drift. | `NOT_STARTED` |
| 9.17 | Knowledge Graph | 9.9, 9.16 (effectively all prior) | Phase 3 | Synthesizes entities/relationships from every other capability's output — correctly sequenced last. | `NOT_STARTED` |

**Note the reordering above:** 9.9 (Root Cause Analysis) is listed right after 9.3,
ahead of 9.4–9.8, because Stage 2 confirmed it as MVP while 9.4–9.8 are Phase 2 — the
table's row order now reflects actual build order; only the ID numbers still reflect
the original dependency-discovery order.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| Add a "Priority (Stage 2)" column; reorder the table so 9.9 (Root Cause Analysis) is listed right after 9.1–9.3, ahead of 9.4–9.8; keep original IDs unchanged | Renumbering all sub-stages so IDs match build order (e.g. Root Cause Analysis becomes 9.4) | Renumbering would churn every "Depends on" reference for no real benefit — IDs are a dependency catalog, priority is a separate, orthogonal fact, and collapsing them invites the same confusion again the next time Stage 2 priority shifts | Engineering Manager |

## Architecture Review checklist (exit criteria, for the *stage as a whole*)

Each sub-stage has its own exit checklist once its README is created. The stage as a
whole is only `APPROVED` when:

- [ ] All sub-stages in the agreed MVP scope (per Stage 2) are `APPROVED`.
- [ ] No sub-stage was merged without a Senior Security Engineer review.
- [ ] No sub-stage's implementation deviated from the frozen Stage 3–8 contracts
      without a corresponding new ADR.
- [ ] `PROGRESS.md` has a dated entry for every sub-stage status change.

## Related docs

- Previous stage: `docs/08-testing-strategy/README.md`
- Next stage: `docs/10-optimization/README.md`
- Sub-stage template: `docs/00-process/templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md`
- `PROGRESS.md` entries tagged Stage 9
