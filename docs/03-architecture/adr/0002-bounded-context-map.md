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
