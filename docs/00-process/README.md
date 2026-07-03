# Engineering Process — the project's constitution

This document defines *how* this project is built. It is stage-gated on purpose: the
goal is not to ship features fast, it is to produce a repository that demonstrates the
judgment of a senior engineering organization. Speed is subordinate to rigor here.

If you are an LLM session picking this project up, start at `MASTER_PROMPT.md`, then
`PROGRESS.md`, then come back here for the mechanics below.

## The 10 stages

| # | Stage | One-line purpose |
|---|---|---|
| 1 | Problem Discovery | Prove a real, specific problem exists before proposing anything |
| 2 | Product Discovery | Turn the problem into a scoped, prioritized product (MVP + roadmap) |
| 3 | Architecture | Decide system boundaries, style (DDD/hexagonal/CQRS/event-driven), and record ADRs |
| 4 | Database | Design persistence per bounded context: schemas, event topics, cache usage |
| 5 | API Design | Define the external contract: OpenAPI, auth model, versioning, webhooks |
| 6 | Sequence Diagrams | Document critical runtime flows end-to-end, including failure paths, before coding |
| 7 | Infrastructure | Make it deployable: Docker/K8s/Helm, CI/CD, observability stack |
| 8 | Testing Strategy | Define the test pyramid, LLM eval approach, coverage gates, Definition of Done |
| 9 | Implementation | Build capability by capability, foundation first, inside the frozen contracts above |
| 10 | Optimization | Harden for real production load: performance, cost, scalability |

Stage 9 is the only stage with sub-stages (see `docs/09-implementation/README.md`) —
it spans months and each of the 17 product capabilities gets its own mini design → build
→ review loop, but always inside the architecture, data model, API, and test strategy
already frozen by Stages 3–8. Sub-stages do **not** re-litigate the platform
architecture; they consume it.

## Why this order, specifically

- Problem before Product: a well-built product for a fabricated problem is still
  worthless. This order forces evidence before scope.
- Product before Architecture: architecture decisions (monolith vs. services, which
  bounded contexts exist) are answers to *product* questions (what capabilities, what
  scale, what data). Deciding architecture first produces solutions looking for a
  problem — a classic over-engineering trap.
- Database → API → Sequence Diagrams, in that order: the data model is the most
  expensive thing to change after the fact (migrations, backfills), so it's fixed
  before the API contract is drawn on top of it, and the API is fixed before the
  runtime flows that call it are diagrammed.
- Infrastructure before Testing Strategy: you need to know the deployment topology
  (what's a container, what's a K8s job, what's a Kafka consumer) before you can
  design a realistic test pyramid (what needs testcontainers, what needs a real
  cluster, what can be unit-tested in isolation).
- Testing Strategy before Implementation: a project that "adds tests later" reliably
  ends up with untested integration seams. Tests are designed as a contract, then
  code is written to satisfy it.
- Optimization last, deliberately: premature optimization before real usage data
  exists is guessing. Optimization here is evidence-driven (benchmarks, load tests),
  not speculative.

## Roles per stage

Each stage is "led" by certain simulated roles and "reviewed" by others. This isn't
ceremony — it changes what questions get asked.

| Stage | Leads | Reviews / signs off |
|---|---|---|
| 1. Problem Discovery | PM, CEO, System Analyst | CTO, Principal SWE |
| 2. Product Discovery | PM, UX Engineer, System Analyst | CEO, CTO |
| 3. Architecture | CTO, Principal SWE, Staff Backend, Staff Platform | Whole eng leadership |
| 4. Database | DB Architect | Principal SWE, Staff Backend |
| 5. API Design | System Analyst, Staff Backend | Principal SWE, UX Engineer |
| 6. Sequence Diagrams | Principal SWE, Staff Backend, Staff Platform | CTO |
| 7. Infrastructure | Senior DevOps, Senior Kubernetes Engineer, Staff Platform | Senior Security Engineer |
| 8. Testing Strategy | Senior SDET, Senior Python Developer | Principal SWE, Senior Security Engineer |
| 9. Implementation | Senior Python Developer, Senior AI Engineer, Senior SDET | Principal SWE, Senior Security Engineer (per sub-stage) |
| 10. Optimization | Staff Backend, Staff Platform, Senior DevOps, DB Architect | CTO |

Cross-cutting, every stage:
- **Engineering Manager** owns `PROGRESS.md` hygiene — no stage is `DONE` without a
  logged entry.
- **Tech Writer** produces or updates the stage's `README.md` and any public-facing
  docs.
- **Open Source Maintainer** keeps repo hygiene (structure, licensing, contribution
  docs) sane, especially from Stage 7 onward when the repo becomes runnable.
- **Hiring Manager (FAANG)** is invoked periodically, not per-stage, as an adversarial
  audit: "does this artifact clear the bar of a senior engineer's GitHub review?" Any
  stage's Architecture Review may pull this role in if quality is in doubt.

## Architecture Review — the gate mechanic

Every stage's `README.md` ends with an **Architecture Review checklist** — its exit
criteria, phrased as verifiable statements, not vibes ("has 3+ named personas with
evidence," not "understands the users"). To close a stage:

1. The leading roles assert the checklist is satisfied, item by item.
2. The reviewing roles (table above) challenge it — specifically look for: weak
   evidence, un-costed trade-offs, scope creep into a later stage, or a decision made
   for convenience rather than merit.
3. If the review finds a gap, the stage status becomes `REVISING`, the gap is logged
   in `PROGRESS.md`, and the team fixes it before moving on — the project does not
   carry known-weak foundations forward "to keep momentum."
4. Once satisfied, the stage becomes `APPROVED`, `PROGRESS.md`'s `CURRENT STATE` moves
   to the next stage, and a log entry records the sign-off.

## Status vocabulary

`NOT_STARTED · IN_PROGRESS · IN_REVIEW · REVISING · APPROVED · BLOCKED`

## Documentation policy

- Stages 1–8 and 10: one `README.md` each, created up front with *scope only*
  (goal, entry criteria, questions, deliverables, exit checklist) — filled in with
  real content when that stage is actually worked.
- Stage 9: one index (`docs/09-implementation/README.md`) listing all sub-stages and
  their dependency order. Each sub-stage's own `docs/09-implementation/9.NN-<slug>/README.md`
  is created **at the moment that sub-stage starts**, from
  `templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md` — never pre-written, so the repo
  never carries speculative or stale documentation for unbuilt features.
- Every ADR (architecture decision record), once Stage 3 begins, lives under
  `docs/03-architecture/adr/NNNN-title.md`, numbered sequentially, immutable once
  accepted (superseded by a new ADR, never edited in place).
- **`docs/OPERATIONS_STRATEGY.md`** (added Stage 9.5, 2026-07-02): a living,
  top-level, cross-cutting strategy document for development sequencing,
  debugging practice, CI/CD activation, and launch — deliberately **not**
  stage-gated, since "how do we keep developing/debugging/shipping" spans
  Stages 7, 8, 9, and 10 and has no single natural home. It references, and
  never contradicts, whatever those stages have already frozen; unlike every
  other doc in this policy, it is expected to be edited in place as reality
  changes, not superseded by a new numbered artifact.

## Templates

- [`templates/STAGE_TEMPLATE.md`](templates/STAGE_TEMPLATE.md) — for Stages 1–8, 10.
- [`templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md`](templates/IMPLEMENTATION_SUBSTAGE_TEMPLATE.md) — for each Stage 9 capability.
