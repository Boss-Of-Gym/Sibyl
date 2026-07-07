# ADR-0002: Bounded context map and GitHub-only MVP scope

**Status:** Accepted (2026-07-02)

## Context

The MVP (Stage 2) covers PR Analysis, Test Impact Analysis, Flaky Detection, and
Root Cause Analysis. These need clear ownership boundaries (ADR-0001 depends on it)
and a decision on which source-control platform(s) are integrated first.

## Decision

**Bounded contexts for MVP:**

| Context | Owns | Notes |
|---|---|---|
| **Ingestion** | Normalizing raw webhook payloads into internal domain events | GitHub adapter only for MVP (see below); GitLab is a second adapter added later inside this same context, not a new context |
| **Test Intelligence** | Test Impact Analysis + Flaky Detection | Combined into one context: both reason over the same "test run history" model, just asking different questions (what's affected vs. what's unstable). Splitting them would duplicate that model. |
| **PR Analysis** | Risk/quality evaluation of a specific change | |
| **Root Cause Analysis** | The "root-cause hypothesis" domain model; consumes PR Analysis + Test Intelligence outputs | Does not own test-run or diff data itself — reads it via events/read models from the other two contexts |
| **Identity/Access** | GitHub App installations, tokens, scoping | |

**Shared kernel (not a bounded context):** LLM Reasoning — a technical port/capability
(no independent domain language) used by PR Analysis and Root Cause Analysis. See
ADR-0005.

**GitHub-only for MVP:** no Stage 1 persona requires GitLab. The GitLab adapter is
explicitly deferred to Phase 2, added as a second adapter inside the Ingestion
context — the domain model of every other context is source-control-platform
agnostic by construction (it operates on normalized internal events, never on raw
GitHub/GitLab payloads directly), so adding GitLab later does not touch PR
Analysis, Test Intelligence, or Root Cause Analysis at all.

## Alternatives considered

- **One bounded context per source-control system** (a "GitHub context" and future
  "GitLab context"). Rejected: these systems have no distinct business domain of
  their own here — they're integration adapters, not domains. Modeling them as
  contexts would put integration concerns where business logic should be.
- **Split Test Impact Analysis and Flaky Detection into separate contexts.**
  Rejected: shared core model (test run history) would be duplicated or require an
  awkward shared-context workaround; combining them is the less-duplicative choice
  given they're both MVP and always evolve together at this stage.
- **Build the GitLab adapter alongside GitHub in MVP** ("for completeness").
  Rejected: no persona evidence justifies the extra integration cost now; the
  domain model is already GitLab-ready via the adapter pattern, so nothing is lost
  by deferring the adapter itself.

## Consequences

- Positive: every MVP capability has an unambiguous home; GitLab support later is
  additive (new adapter), not invasive.
- Negative: Test Intelligence is a slightly coarser-grained context than a strict
  1:1 capability-to-context mapping — acceptable since DDD contexts are about
  shared domain language, not a 1:1 feature mapping.
- Follow-up: if Flaky Detection and Test Impact Analysis diverge significantly in
  their data models during Stage 4, this combined-context decision should be
  revisited rather than forced.

## Addendum (Stage 9.5, 2026-07-02): CI/CD Optimization joins Test Intelligence

CI/CD Optimization (Phase 2, per Stage 2) was never assigned a bounded context —
it wasn't one of the four MVP capabilities this ADR originally scoped. Its actual
job (distinguish a chronically slow test from a flaky one, rank tests by
optimization value) reasons over the exact same "test run history" model
(`test_run`/`test_case_result`) that justified combining Test Impact Analysis and
Flaky Detection above — not a new domain language, the same one asked a third
question. **Decision: CI/CD Optimization is a third capability inside Test
Intelligence**, not a new context.

Alternatives considered:
- **New "Pipeline Optimization" bounded context.** Rejected: would duplicate the
  test-run-history model a third time (the same argument this ADR already made
  against splitting Flaky Detection out), and there is no distinct ubiquitous
  language here — "slow," "flaky," and "affected" are all properties of the same
  underlying test-run fact, not three different domains.
- **Model it as a shared kernel, like LLM Reasoning.** Rejected: shared kernel in
  this project specifically means a cross-context *technical* capability with no
  domain language of its own (a port). CI/CD Optimization has real domain
  meaning (duration trends, optimization ranking) — it belongs inside a context,
  not floating as a technical utility.

Consequence: Test Intelligence now owns three capabilities on one shared data
model. This is the same trade-off already accepted for two; a fourth would be
the point to revisit whether this context has grown too coarse (not yet).

## Addendum (Stage 9.4, 2026-07-02): Coverage Intelligence joins Test Intelligence — and the revisit point above is now reached

Coverage Intelligence (Phase 2) is Stage 9's own roadmap description: "builds
on the test-impact data model to reason about coverage gaps meaningfully
rather than raw percentages." Same reasoning as the Stage 9.5 addendum above —
it reads `test_case_result`/`test_run` history and PR-changed-file data
already owned by this context, not a new domain language. **Decision:
Coverage Intelligence is a fourth capability inside Test Intelligence.**

This is exactly the "fourth" the Stage 9.5 addendum flagged as "the point to
revisit whether this context has grown too coarse." Revisited, explicitly:
still not too coarse — all four capabilities (impact, flakiness, duration,
coverage) answer different questions about the *same* underlying fact ("a
test ran, what does that tell us"), none has its own business rules or
vocabulary independent of that fact, and none needs a different persistence
or event-consumption shape than the others already use. Root Cause Analysis,
by contrast, was correctly given its own context because a "hypothesis" is a
real, distinct domain concept — Coverage Intelligence has no equivalent.

**A concrete line, not another vague "revisit later":** if a fifth capability
is ever proposed for Test Intelligence, that is a mandatory context-split
evaluation before implementation starts, not an optional revisit — four
capabilities sharing one data model is defensible on the reasoning above; a
fifth is where "coarse-grained context" starts looking like "everything test-
related dumped in one place regardless of whether it shares real domain
language." This threshold is deliberately concrete so a future session can't
talk itself into a fifth the same easy way a third and fourth were justified.

Alternatives considered:
- **New context.** Rejected for the same reason as 9.5's addendum: no
  distinct ubiquitous language, would duplicate the test-run-history model a
  fourth time.
- **Shared kernel.** Rejected for the same reason as 9.5's addendum: this has
  real domain meaning (coverage gaps, ranked), not just a technical port.

Consequence: Test Intelligence now owns four capabilities on one shared data
model — the accepted ceiling per the threshold above.

## Addendum (Stage 9.6, 2026-07-02): Dependency Analysis is a new bounded context — the mandatory evaluation the Stage 9.4 threshold anticipated

Dependency Analysis (Phase 2) is the first capability since the original MVP
freeze that does **not** join an existing context. Stage 9's own roadmap
description calls it "independent of the PR/test-signal chain," and its
dependency list is just `9.0` — unlike Coverage Intelligence and CI/CD
Optimization, which both also depended on Test Intelligence's own prior
sub-stages (9.2, 9.3). Running the mandatory context-split evaluation the
Stage 9.4 addendum set up for exactly this situation: a dependency
manifest (package name, version, ecosystem, direct/transitive) shares **no**
ubiquitous language with "a test ran, what does that tell us" — it's a
different fact about the repository entirely, closer in kind to PR
Analysis's diff metadata than to anything Test Intelligence already owns.
**Decision: Dependency Analysis is a new bounded context**, not a fifth
capability inside Test Intelligence.

This is the threshold working as designed: the Stage 9.4 addendum didn't ban
a fifth Test Intelligence capability outright, it required an actual
evaluation before proceeding — and here the evaluation concludes the
opposite of 9.4/9.5's, on the same reasoning framework applied honestly
rather than defaulted into. Test Intelligence remains at four capabilities.

Alternatives considered:
- **Fifth capability inside Test Intelligence.** Rejected: no shared domain
  language with test-run history; would be "everything analytical dumped in
  one place" rather than a real DDD boundary, exactly what the Stage 9.4
  threshold exists to catch.
- **Shared kernel.** Rejected for the same reason as the 9.4/9.5 addenda:
  dependency data has real domain meaning of its own (a package graph), not
  a technical port with none.

Consequence: a sixth bounded context and Postgres schema
(`dependency_analysis`), following the exact same pattern as the original
five — own schema, own migration branch, no cross-schema FKs, `installation_id`
scoping key, transactional outbox for anything it publishes (nothing yet, see
the Stage 4 addendum).

## Addendum (Stage 9.8, 2026-07-02): API Evolution Tracking joins Dependency Analysis — the same evaluation, run in the joining direction this time

API Evolution Tracking (Phase 2) has the identical evidence tier to
Dependency Analysis — "market/competitive only," no Stage 1 persona, per
`docs/02-product-discovery/README.md`. Stage 9's own roadmap description
("needs dependency/manifest awareness (9.6) plus [diffing] to detect
breaking changes") makes the ubiquitous-language question direct: does
"classify a dependency version change as breaking" share a domain fact with
"store a dependency manifest snapshot"? Running the same evaluation
framework the Stage 9.4/9.6 addenda established — this time concluding the
other way from 9.6's own precedent: **yes**, it's the same fact
(`dependency_manifest_snapshot`), asked a new question, the same relationship
Test Impact Analysis/Flaky Detection/CI/CD Optimization/Coverage
Intelligence already have inside Test Intelligence. **Decision: API
Evolution Tracking is a second capability inside Dependency Analysis**, not
a new context.

This scope decision (see the Stage 9.8 sub-stage doc for the full
discussion, presented to and confirmed by the user before implementation)
deliberately narrows "API Evolution Tracking" to **dependency-version
breaking-change detection via semver classification**, not literal
OpenAPI-spec diffing (parsing and comparing a repository's own
`openapi.yaml` across commits) — the roadmap description is read narrowly on
purpose: literal spec-diffing would need an entirely new ingestion source
(a repository's own API spec, a different fact than a dependency graph,
which *would* argue for a new context) for a capability with zero persona
evidence. Real OpenAPI-spec diffing remains a distinct, larger, undecided
future capability if evidence ever justifies it — not assumed as part of
this sub-stage by default.

Alternatives considered:
- **New context for literal OpenAPI-spec diffing.** Rejected for scope, not
  architecture: parsing and storing a repository's own API spec history is a
  different fact than a dependency graph (would itself argue for a new
  context, correctly, if built) — but building that new ingestion surface
  and diff engine for a zero-evidence capability is disproportionate. Noted
  as a real future option, not built now.
- **Fifth-capability-style new context just for this.** Rejected: would fail
  the same ubiquitous-language test 9.6 itself failed when it *was*
  proposed as a Test Intelligence capability — the difference here is this
  one actually passes.

Consequence: `dependency_analysis` now owns two capabilities on one
data model (manifest storage, breaking-change diffing) — the same
"a few capabilities sharing one real domain fact" pattern already
established and bounded (at four) inside Test Intelligence.

## Addendum (Sub-stage 9.10, 2026-07-07): Regression Prediction is a new, seventh bounded context

Unlike every prior addendum, 9.10's two dependencies —
`test_intelligence` (9.2, Test Impact Analysis) and `root_cause_analysis`
(9.9) — live in *different* existing contexts, so "join the context my
dependencies already live in" isn't a single well-defined option the way it
was for 9.4/9.5/9.8. Running the same ubiquitous-language evaluation
framework against both candidates:

- **Does it share language with Root Cause Analysis?** RCA answers "why did
  *this specific* failure happen" — one event, backward-looking,
  correlating three inputs that all describe the same failure. Regression
  Prediction answers "how likely is *this new, not-yet-failed* PR to cause
  a regression" — forward-looking, aggregating a *history* of past
  hypotheses into a pattern, not correlating simultaneous facts about one
  event. Different question, different temporal direction, about a
  different subject (a future PR vs. a specific past failure). **Not the
  same fact.**
- **Does it share language with PR Analysis?** PR Analysis scores
  "engineering risk" from diff *structure* (size, area, historical flaky
  proximity) via LLM narrative judgment — no historical failure-pattern
  correlation involved. Regression Prediction's score is explicitly
  *grounded in* historical root-cause data, not diff structure alone.
  Adjacent, but a genuinely different input methodology, not "the same
  question asked to a different capability."

Both comparisons land on "different fact, different question," which is the
same signal that already correctly split Dependency Analysis (9.6) out on
its own. Architecturally, Regression Prediction turns out to be a much
closer structural sibling of the **MVP capabilities themselves**
(PR Analysis, Root Cause Analysis) than of anything already in Phase 2:
correlate multiple upstream signals into a bounded context of its own, call
an LLM through the same `ReasoningPort`/`GuardedReasoningPort`/
`AnthropicReasoningPort` shape, publish a completion event, post a GitHub
Check — exactly Root Cause Analysis's own shape, aimed forward instead of
backward. This also matches this project's own stated LLM thesis
(`MASTER_PROMPT.md` §2, `docs/01-problem-discovery/README.md`'s "why an LLM
specifically" section): synthesis across noisy, cross-system historical
signal, not a bespoke statistical/ML model this project has no other
precedent for building.

Alternatives considered:
- **Join `root_cause_analysis` as a second capability, read-time only (no
  new ingestion), mirroring how API Evolution Tracking joined Dependency
  Analysis.** Rejected: unlike 9.8 (which computes a diff from two rows
  already owned by the *same* table), Regression Prediction's trigger
  (`ingestion.pr-changed`) and its correlation subject (a *future* PR) are
  not natural extensions of `root_cause_hypothesis`'s own domain language —
  forcing it in would replicate the exact "everything analytical dumped in
  one place" failure mode the Stage 9.4 threshold was built to catch,
  just one context over.
- **A bespoke statistical/ML prediction service outside the
  ReasoningPort pattern.** Rejected: no ADR (including ADR-0005, this
  project's LLM integration architecture) has ever established an ML
  training/serving pattern, and introducing one for a single,
  weakly-evidenced (market/competitive only) capability is unjustified
  operational and architectural cost. The existing LLM-reasoning-over-
  correlated-signal pattern already fits this problem shape.

Consequence: a seventh bounded context and Postgres schema
(`regression_prediction`), following the same pattern as every other
context — own schema, own migration branch, no cross-schema FKs,
`installation_id` scoping key, transactional outbox, its own
`pull_request_regression_prediction`/`historical_regression_projection`
tables, a `regression-prediction.completed` topic, and a GitHub Checks
postback. Required one contract change to an already-frozen event: the
`root-cause.hypothesis-ready` payload gained a `suspected_file_path` field
(previously omitted) so Regression Prediction can build its historical
index by file — logged as a Stage 4 addendum, not a silent change.

## Addendum (Sub-stage 9.7, 2026-07-07): Engineering Metrics is a new, eighth bounded context — closing the deferral honestly by narrowing scope, not by joining an existing context

9.7 (Engineering Metrics) was deliberately deferred earlier in Phase 2:
Stage 9's roadmap description calls for "DORA-style metrics," and full DORA
(deployment frequency, lead time to production, change failure rate, MTTR)
genuinely requires deployment/incident event data this project has no
ingestion source for — fabricating it was rejected then and is still
rejected now. Revisiting the deferral rather than leaving it open-ended:
9.7's own frozen dependency list is just `9.0`, `9.1`, `9.3` — it does not
depend on any deployment infrastructure at all. Read literally, the
buildable subset is narrower than full DORA: aggregate PR-flow (cycle time)
and CI-health (success rate, duration) signal into read-time statistics
over a time window. That subset is real, honestly scoped, and buildable
today without inventing data.

Running the same ubiquitous-language evaluation against both existing
contexts whose data this subset touches:

- **Does it share language with PR Analysis?** PR Analysis answers "how
  risky is *this one* PR's diff" — a single-subject, structural judgment
  produced once per PR via LLM narrative reasoning. Engineering Metrics
  answers "how healthy is the PR flow *in aggregate* over the last N days" —
  a population-level statistic (median cycle time across many PRs) that
  needs lifecycle timestamps (`opened_at`/`merged_at`/`closed_at`) PR
  Analysis's own domain model never tracked and has no reason to. Different
  subject (one PR vs. a population of PRs), different question shape
  (narrative risk judgment vs. arithmetic aggregation). **Not the same
  fact.**
- **Does it share language with Test Intelligence?** Test Intelligence's
  CI-run-derived signals (flakiness, duration, coverage) are all keyed by
  `test_identifier` — "is *this specific test* flaky/slow." Engineering
  Metrics needs per-*CI-run* aggregates (did the run pass overall, how long
  did the whole run take) across a population of runs, not per-test
  history. Same raw event (`ingestion.ci-run-completed`) as a producer, but
  a different unit of analysis and a different question ("is the pipeline
  healthy in aggregate" vs. "is this one test reliable"). **Not the same
  fact either.**

Both comparisons land on "different question, different unit of analysis,"
the same signal that split Dependency Analysis (9.6) and Regression
Prediction (9.10) out on their own. **Decision: Engineering Metrics is a
new, eighth bounded context.**

Unlike every other context so far, this one needs **no new Kafka topic at
all** — it has nothing to publish (no downstream consumer needs "PR/CI
metrics were recomputed"), and it needs no new *producer* either: it
consumes the two raw ingestion topics (`ingestion.pr-changed`,
`ingestion.ci-run-completed`) directly, the same topics Test Intelligence
and PR Analysis already consume, as an independent Kafka consumer group
reading its own local projection. This is the cheapest possible integration
shape in this system — cheaper even than 9.10's, which still needed a new
topic and a frozen-contract amendment.

Alternatives considered:
- **Extend PR Analysis's `pull_request` table with `merged_at`/`closed_at`
  and build the read API there.** Rejected: would conflate a per-PR risk
  score with a population-level flow statistic in one context's schema —
  the same "everything dumped in one place" failure mode the Stage 9.4
  threshold exists to catch, just against a different context. Also
  unnecessary in practice: `ingestion.pr-changed` already carries the full
  raw GitHub webhook payload verbatim, including `merged_at`/`closed_at`,
  so no upstream context needs modification at all — any new consumer can
  read fields no *existing* consumer happened to model yet.
- **Build full DORA now, backfilling synthetic deployment data.** Rejected
  outright: fabricating evidence to unblock a roadmap item violates this
  project's evidence-before-speculation discipline; a real deployment
  ingestion source is still genuinely absent infrastructure, not a design
  choice to route around.
- **Pre-computed rollup tables (recompute-on-write), matching neither
  existing pattern exactly.** Rejected: read-time aggregation over stored
  per-PR/per-run rows, mirroring Test Intelligence's own
  `list_slow_tests`/`list_coverage_gaps` read-time ranking, keeps the write
  path a plain upsert and avoids a second source of truth for numbers a
  30-day window query can compute cheaply on demand.

Consequence: an eighth bounded context and Postgres schema
(`engineering_metrics`), with `pr_lifecycle_projection` and
`ci_run_projection` as local, per-window read-side projections built from
the two raw ingestion topics — no outbox table (first context to genuinely
need none from day one), no new topic, no new event contract. Full DORA
(deployment frequency, lead time to production, change failure rate, MTTR)
remains explicitly deferred, now for a documented reason (no deployment
ingestion source) rather than an open-ended "later."

## Addendum (Sub-stage 9.11, 2026-07-07): Release Risk Analysis is a new, ninth bounded context — fusing three signals that span three different existing contexts, and what "release" honestly means here

9.11's own frozen dependency list (`9.4` Coverage Intelligence, `9.7`
Engineering Metrics, `9.10` Regression Prediction) already signals
something structurally different from every addendum before it: its inputs
live in **three different** existing contexts, not one (9.4/9.5/9.8's join
cases) or two (9.10's fan-in case). Running the same ubiquitous-language
evaluation this project has applied at every prior fork, against all three
candidates:

- **Coverage Intelligence** answers "which files/areas lack coverage right
  now" — a repository-wide structural gap, not something scoped to a
  specific PR or moment of decision.
- **Engineering Metrics** answers "how healthy is the PR flow and CI
  pipeline in aggregate over a stated window" — a reporting-shaped,
  calendar-windowed statistic.
- **Regression Prediction** answers "how likely is *this* PR to cause a
  regression" — a single-PR, LLM-correlated probability.

Release Risk Analysis asks a fourth, different question: "given all three
of the above, is *this* PR safe to ship right now" — a weighted fusion of
three independently-computed numbers into one decision-support score, not
a restatement of any one of them. None of the three pass the "same fact"
test individually, and fusing three genuinely different facts into one
new fact is itself evidence of a new bounded context, the same reasoning
that already split Dependency Analysis (9.6) and Regression Prediction
(9.10) out on their own — just a three-way version of the same test.
**Decision: Release Risk Analysis is a new, ninth bounded context.**

**What "release" honestly means, given this project has no deployment/tag
ingestion source anywhere** (the same gap that keeps full DORA deferred
under the Sub-stage 9.7 addendum above): Stage 9's roadmap text says
"release-level score," but there is no ingested entity called a release.
Re-reading Stage 1's own persona evidence (`docs/01-problem-discovery/README.md`,
persona 3, "small-team release decision-maker") shows the actual described
pain is a **merge-time decision** — "is it OK to ship right now" — not a
literal post-merge deployment artifact. The honestly-buildable
interpretation, consistent with the persona's real story and with every
other capability in this system being PR/commit-scoped, is: **a per-PR
merge-readiness score**, computed at the moment a Regression Prediction
result becomes available for that PR. This mirrors the Sub-stage 9.7
addendum's own move (narrowing an over-claiming roadmap phrase to what the
real data model supports) rather than inventing a "release" concept this
system has no evidence for.

**No LLM in this capability** — the fusion itself is a deterministic
weighted average of three already-computed numbers
(`compute_release_risk_score`), matching Engineering Metrics's "pure
statistics" shape rather than the MVP correlate-then-call-LLM shape. This
is deliberate: Stage 9's own roadmap text reserves the LLM-generated
narrative for 9.12 (Release Advisor), which "turns the risk score into an
actual LLM-generated go/no-go narrative" — 9.11 produces the score, 9.12
(not yet built) will narrate it.

**Getting three cross-context signals without violating the
no-cross-schema-reads rule** — none of the three signals are read via a
synchronous cross-context call:
- Regression Prediction already publishes `regression-prediction.completed`
  — consumed directly into a local projection, the ordinary case.
- Engineering Metrics publishes nothing (by its own Stage 4 addendum
  design). Rather than depending on its schema or API, Release Risk
  Analysis builds its **own** tiny local projection consuming
  `ingestion.ci-run-completed` directly — the same "cheapest integration,
  consume the raw topic directly" pattern Engineering Metrics itself
  established, computed independently rather than through Engineering
  Metrics at all.
- Coverage Intelligence (inside Test Intelligence) published no event of
  any kind — a real gap, not a design choice, per the Stage 4 addendum's
  own "no consumer, no event" reasoning at the time. A real consumer now
  exists, which is exactly the condition that same addendum said would
  justify adding one. **Required amending an already-frozen event
  contract**: Test Intelligence now publishes a new
  `test-intelligence.coverage-computed` event per file whenever coverage is
  recomputed — the same class of change as 9.10's `suspected_file_path`
  amendment to `root-cause.hypothesis-ready`.

**Trigger design mirrors Root Cause Analysis's own multi-input correlation
(§4)**: rather than triggering on the earliest-arriving signal (which would
race against the other two), Release Risk Analysis recomputes on
`regression-prediction.completed` — the rarest, slowest-arriving, and most
PR-specific signal — reading its own already-materialized local
projections (recent CI runs, current coverage-by-file) for the other two.
CI health is computed over the **most recent 20 CI runs** (a fixed sample
size, mirroring Test Intelligence's own `get_recent_statuses`/
`get_recent_durations` convention), not a calendar window like Engineering
Metrics — a deliberately different convention for a differently-shaped
question (a recency-weighted reliability signal feeding a decision score,
not a reporting-window statistic).

Alternatives considered:
- **Join `regression_prediction` as a second capability**, mirroring how
  API Evolution Tracking joined Dependency Analysis. Rejected: unlike 9.8
  (a diff computed from two rows already owned by the same table), two of
  Release Risk Analysis's three inputs (coverage, CI health) have nothing
  to do with Regression Prediction's own domain — forcing it in would
  recreate the exact "everything dumped in one place" failure mode the
  Stage 9.4 threshold exists to catch, one context over.
- **Treat "release" as requiring real deployment/tag data and defer 9.11
  entirely**, the same way full DORA remains deferred. Rejected: 9.11's own
  frozen dependency list never actually required deployment data — only
  9.4/9.7/9.10, all already built — so deferring further would be
  under-building relative to what the frozen contracts actually promise,
  not an honest gap the way full DORA is.

Consequence: a ninth bounded context and Postgres schema
(`release_risk_analysis`), with `regression_signal_projection`,
`ci_health_projection`, and `coverage_signal_projection` as local
projections of the three upstream signals, a `release_risk_assessment`
result table (append-only, like `regression_prediction`/
`pr_risk_assessment` — "latest" is the newest `computed_at`), and its own
outbox (`release-risk.completed`, with no consumer yet — a known,
frozen-roadmap consumer, 9.12 Release Advisor, not speculative
infrastructure the way an unconsumed event would otherwise be). Required
amending Test Intelligence's already-frozen Stage 4 contract to add
`test-intelligence.coverage-computed`.
