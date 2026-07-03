# ADR-0007: MVP scalability targets (assumed, not measured)

**Status:** Accepted (2026-07-02) — to be revisited with real data in Stage 10

## Context

"Web scale" is not a design target. Later stages (database indexing, Kafka
partitioning, API performance work) need concrete numbers to design against, even
if those numbers are reasoned assumptions rather than measured production data —
this project has no production traffic yet.

## Decision

Design against these assumptions, grounded in the small-team reality established in
Stage 1 (not a large-org scale):

- Up to **50 repositories** per installation.
- Up to **200 pull requests/day** across those repositories.
- Up to **5,000 CI job-completion events/day**.
- **p95 API read latency < 300ms** for fetching an existing analysis result.
- **Analysis available within 2 minutes** of the triggering CI run completing.

## Alternatives considered

- **No stated targets ("scale as needed").** Rejected: leaves Stage 4 (indexing,
  partitioning) and Stage 7 (resource limits) guessing, which is the exact
  "web-scale hand-waving" this stage's own checklist forbids.
- **Large-org targets** (1000s of repos, tens of thousands of events/day). Rejected:
  not grounded in any Stage 1 evidence — all 3 evidenced personas are small-team
  contexts; designing for a scale with no evidence behind it is the same mistake as
  keeping an unevidenced persona, one level down in the stack.

## Consequences

- Positive: subsequent stages have concrete numbers to design against instead of
  adjectives.
- Negative: these are assumptions, not measurements — if wrong, some Stage 4/7
  decisions (indexing strategy, resource requests) may need revisiting.
- Follow-up: Stage 10 (Optimization) replaces these assumptions with real load-test
  results and benchmarks; this ADR is explicitly provisional in a way the others
  are not.
