# Sub-stage 9.NN — <Capability Name>

> Template for each Stage 9 capability. Create this file at
> `docs/09-implementation/9.NN-<slug>/README.md` **at the moment work on the
> capability starts** — not before. Delete this blockquote once filled in.

**Status:** `NOT_STARTED | IN_PROGRESS | IN_REVIEW | REVISING | APPROVED | BLOCKED`
**Depends on:** <sub-stage IDs / platform foundation>
**Owner roles:** <e.g. Senior Python Developer, Senior AI Engineer>
**Reviewer roles:** Principal SWE, Senior Security Engineer

## Problem / JTBD reference

Which Stage 1 persona and Stage 2 job-to-be-done this capability serves. Link, don't
restate: `docs/01-problem-discovery/README.md`, `docs/02-product-discovery/README.md`.

## Scope

- In scope: ...
- Explicitly out of scope (this pass): ...

## Contracts consumed (frozen upstream, not re-decided here)

- API surface: relevant section of `docs/05-api-design/`
- Data model: relevant section of `docs/04-database/`
- Runtime flow: relevant diagram in `docs/06-sequence-diagrams/`

## Design notes specific to this capability

Anything this capability needs that isn't already covered by the platform-wide
architecture (e.g. a specific prompt strategy, a specific ML/heuristic approach, a
specific third-party API quirk). This is implementation detail, not new architecture —
if it turns out to require an architectural change, that goes back through Stage 3 as
an ADR, not decided ad hoc here.

## Test plan

Per `docs/08-testing-strategy/README.md`: unit / contract / integration / e2e / LLM
eval coverage specific to this capability.

## Observability

Metrics, traces, and logs this capability emits (names, cardinality, dashboards).

## Security considerations

Data sensitivity, auth scopes touched, threat-model notes specific to this capability.

## Definition of Done

- [ ] Meets the platform-wide DoD checklist (`docs/08-testing-strategy/README.md`)
- [ ] Sub-stage-specific criteria: ...

## Changelog

| Date | Change |
|---|---|
| | |
