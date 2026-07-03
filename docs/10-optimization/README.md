# Stage 10 — Optimization

**Status:** `NOT_STARTED`
**Leads:** Staff Backend Engineer, Staff Platform Engineer, Senior DevOps Engineer, DB Architect
**Reviewers:** CTO
**Entry criteria:** Stage 9 (Implementation) `APPROVED` for the agreed MVP scope and running.

## Goal

Harden the platform for real production load using evidence, not speculation.
Optimization is placed last deliberately: optimizing before real usage patterns exist
is guessing, and guessed optimizations frequently add complexity for no measured
benefit. Everything in this stage starts from a benchmark or load test, not a hunch.

## Key questions / activities

- **LLM cost and token optimization**: measure actual token spend per analysis (e.g.
  per PR analyzed, per release-risk score computed), identify the highest-cost
  capabilities, and evaluate caching, prompt compression, or model-tiering
  (cheaper model for simple cases, escalate to a stronger model only when needed).
- **Database query/index tuning**: driven by actual slow-query logs and `EXPLAIN
  ANALYZE` output from the running system, not preemptive indexing.
- **Caching strategy validation**: revisit the Stage 4 Redis usage catalog against
  measured hit rates — remove caches that don't earn their complexity, add ones the
  data shows are needed.
- **Load and chaos testing**: realistic load profiles (concurrent webhook bursts,
  large-monorepo PR analysis, Kafka consumer lag under backpressure) and fault
  injection (broker unavailability, LLM provider timeout/rate-limit, database
  failover) — validate the failure/retry paths designed in Stage 6 actually hold up.
- **Scalability validation against Stage 3 targets**: confirm (or correct) the
  scalability assumptions made in Stage 3 with real benchmark numbers.
- **Cost model**: total cost per unit of value (e.g. cost per PR analyzed, per
  release-risk report) combining infra and LLM spend — a number a real engineering
  org would actually track.

## Deliverables

- Before/after performance benchmarks for each optimization made.
- Load test reports against the Stage 3 scalability targets.
- Chaos/fault-injection test results against the Stage 6 failure paths.
- A quantified cost model (infra + LLM spend per unit of value).
- A hardening changelog: what changed, why, and what evidence justified it.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| | | | |

## Architecture Review checklist (exit criteria)

- [ ] Every optimization made is backed by a before/after benchmark — no unmeasured
      "this should be faster" changes.
- [ ] Load tests confirm (or have corrected, with a logged decision) the Stage 3
      scalability targets.
- [ ] Chaos/fault-injection tests confirm the Stage 6 failure/retry paths behave as
      designed under real fault conditions.
- [ ] A cost-per-unit-of-value number exists and is defensible.
- [ ] No optimization introduced a regression in the Stage 8 test suite or coverage
      gate.
- [ ] CTO has reviewed the hardening changelog against the original Stage 1 problem
      statement — does the system now actually perform well enough to solve it.
- [ ] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Previous stage: `docs/09-implementation/README.md`
- `PROGRESS.md` entries tagged Stage 10
