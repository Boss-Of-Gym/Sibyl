# Stage 2 — Product Discovery

**Status:** `APPROVED` (2026-07-02)
**Leads:** Product Manager, UX Engineer, System Analyst
**Reviewers:** CEO, CTO
**Entry criteria:** Stage 1 (Problem Discovery) `APPROVED`.

## Goal

Convert the validated problem into a scoped, sequenced product: which of the 17
candidate capabilities ship first, why, and in what order the rest follow. This stage
produces the MVP definition that Stage 3 (Architecture) is designed around — the
architecture must not be drawn before this scope exists, or it will be guessing at
the wrong shape.

## Key questions / activities

- **Score every candidate capability** (PR Analysis, Root Cause Analysis, Test Impact
  Analysis, Regression Prediction, Release Risk Analysis, API Evolution Tracking,
  Flaky Detection, Coverage Intelligence, AI Documentation, Test Generation, Incident
  Analysis, CI/CD Optimization, Dependency Analysis, Engineering Metrics, Release
  Advisor, Architecture Insights, Knowledge Graph) against the Stage 1 personas: which
  JTBD does it serve, how strong is the evidence, what data sources does it need, and
  what does it depend on from other capabilities?
- **Define the MVP cut**: the smallest set of capabilities that (a) shares a data
  pipeline/integration surface to keep initial integration cost low, (b) is
  independently demonstrable and valuable without the rest of the roadmap, and (c)
  proves the "LLM synthesis across existing signals" thesis from Stage 1 — not just a
  metrics dashboard.
- **Sequence the remaining capabilities into phases**, with an explicit dependency
  rationale (e.g., capabilities that fuse multiple other capabilities' outputs, like
  Release Advisor or Knowledge Graph, must come after their inputs exist and are
  trustworthy).
- **Define success metrics**: a north-star metric and 2-4 guardrail metrics that would
  let you tell, honestly, whether the product works — not vanity metrics.
- **Define core user journeys** (UX Engineer): how does a target persona actually
  interact with this — CLI, web dashboard, API/webhook-driven, IDE/PR-comment
  integration, ChatOps? This decision has real architectural consequences for Stage 3
  and Stage 5, so it must be made here, deliberately, not defaulted to "a dashboard"
  out of habit.
- **Positioning**: is this an EM-facing product, a platform-team-facing product, or
  both — and does that change the MVP cut?

## Deliverables

- Capability scoring matrix (impact × feasibility × data-availability × dependency).
- MVP definition: the exact capability set for v1, with rationale tracing to Stage 1.
- Phased roadmap (Phase 1/2/3) for the remaining capabilities, with dependency
  rationale for the ordering.
- Success metrics (north-star + guardrails).
- Core user journeys / interaction model.
- Updated `docs/09-implementation/README.md` sub-stage ordering, if Product Discovery
  changes the dependency assumptions made there.

## Findings (final — approved 2026-07-02)

### Capability scoring vs. Stage 1 evidence

Only 3 of 17 capabilities trace directly to a first-hand-evidenced Stage 1 persona.
Being honest about that (same discipline as dropping the unevidenced EM persona in
Stage 1) drives the cut below rather than picking capabilities because they sound
impressive.

| Capability | Evidence strength | Persona |
|---|---|---|
| PR Analysis | First-hand | #3 (ad hoc code-quality gate) |
| Flaky Detection | First-hand | #2 (chronic vs. one-off), secondary #1 |
| Root Cause Analysis | First-hand | #1 (manual code-tracing to find failure origin) |
| Test Impact Analysis | None directly — required as *technical* input to Root Cause Analysis | — (infrastructure, not persona-evidenced) |
| CI/CD Optimization, Architecture Insights | Secondary/indirect | #2, #3 |
| Everything else (11 capabilities) | Market/competitive only, same evidence class as the dropped EM persona | — |

### MVP (Phase 1) — confirmed

**PR Analysis + Flaky Detection + Test Impact Analysis + Root Cause Analysis.**

Three of these are directly evidenced; Test Impact Analysis is included not because
a persona demanded it, but because Root Cause Analysis technically depends on it
(per the Stage 9 dependency ordering — you can't explain "why did this test fail"
without first knowing "what changed that this test could plausibly be affected by").
This is worth being explicit about, the same way Stage 1 was explicit about
market-evidenced vs. first-hand: **Test Impact Analysis is enabling infrastructure
in this MVP, not a headline feature.**

Deliberately **excluded from MVP**: Release Risk Analysis, Release Advisor, Incident
Analysis, Knowledge Graph — all of these *fuse* other capabilities' outputs and
would be fusing signal that doesn't exist yet. Building them now would mean building
on invented inputs — exactly the mistake Stage 1 exists to prevent, one level down.

### Phased roadmap — confirmed

- **Phase 1 (MVP):** PR Analysis, Test Impact Analysis, Flaky Detection, Root Cause
  Analysis.
- **Phase 2:** CI/CD Optimization, Coverage Intelligence, Engineering Metrics,
  Dependency Analysis, API Evolution Tracking, Regression Prediction — natural
  extensions of Phase 1's data, still plausible even without direct persona evidence
  because they reuse Phase 1's signal rather than inventing new integration surface.
- **Phase 3:** Release Risk Analysis, Release Advisor, Incident Analysis, AI
  Documentation, Test Generation, Architecture Insights, Knowledge Graph — the
  fusion/generative capabilities, correctly last because they depend on Phase 1/2
  being trustworthy first.

### Success metrics — confirmed

- **North star:** for a sample of real historical test failures, % where Root Cause
  Analysis's top suggested cause matches the actual fix commit (measured against a
  labeled eval set — ties directly into the Stage 8 LLM-eval strategy).
- **Guardrails:** false-positive rate on Flaky Detection (crying wolf destroys
  trust faster than missing a real flake); LLM cost per analysis (sustainability);
  time from "PR opened" to "analysis available" (must beat the human noticing on
  their own, or it's dead weight).

### Interaction model — decided

**GitHub-native surfaces first** (PR check annotations / review comments), **REST
API second**, **CLI third** — a standalone web dashboard is explicitly *not* Phase
1. Reasoning: Stage 1's own problem statement is "signal already exists but isn't
connected at the moment it's needed." The moment it's needed is *inside the PR
review*, not in a separate tab. Shipping a dashboard first would repeat the exact
mistake being solved — one more place to check instead of zero. A dashboard becomes
justified later (Phase 2+) once there's cross-PR/cross-time signal worth
visualizing (Release Risk Analysis, Engineering Metrics, Knowledge Graph), which a
PR comment structurally cannot show.

**Binding architectural constraint from this decision** (carried into Stage 3):
analysis logic must not know or care that its output is rendered as a PR comment —
it produces a structured result through the API; *a GitHub Checks adapter is just
one consumer of that API*, not where the logic lives. This is what keeps a later
GitLab surface or dashboard a matter of adding a consumer, not reworking the core.

**Secondary rationale:** the user is targeting backend/platform/SDET/AI engineering
roles, not frontend. Investing MVP effort in API/backend depth (webhook handling,
event pipeline, Checks API integration) rather than a polished frontend is a
deliberate portfolio-fit decision on top of the Stage 1 evidence, not just a
byproduct of it. The visual-portfolio cost this trades away (a dashboard
screenshot) is accepted knowingly — see Decisions log.

### Positioning — confirmed

IC-facing (SDET, platform/CI engineer, the person reviewing the diff) — not
EM-facing — for Phase 1, directly following from which personas actually have
first-hand evidence. EM-facing framing (release risk rollups, team-level metrics) is
Phase 2/3 territory, once Release Risk Analysis and Engineering Metrics exist.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| Interaction model: GitHub-native (PR checks/comments) + API first; no standalone dashboard in Phase 1 | Web dashboard as the primary Phase 1 surface | The 3 evidenced Stage 1 problems are single-artifact-scoped (one PR, one test, one pipeline run), not cross-time/aggregate — a dashboard's core value (trends, rollups) doesn't apply yet; building one now would also repeat the exact "one more tab to check" failure mode Stage 1 identified. Deferred, not eliminated: revisited once Phase 2/3 fusion capabilities (Release Risk Analysis, Engineering Metrics, Knowledge Graph) need an aggregate view. | CEO / CTO / user |
| Analysis logic decoupled from presentation (GitHub Checks adapter is one API consumer, not where logic lives) | Building the GitHub Checks integration directly into the analysis service | Would lock Phase 2 GitLab support or a future dashboard into a rework instead of "add a consumer" | CTO |
| MVP effort favors backend/API depth over frontend polish | Splitting effort evenly across backend and a minimal frontend | Explicit portfolio-fit decision: target roles (backend/platform/SDET/AI engineering) are better served by integration/API depth than frontend polish; the traded-away visual-demo value is accepted knowingly | User |
| MVP = PR Analysis + Test Impact Analysis (infra) + Flaky Detection + Root Cause Analysis | Cutting to 3 persona-evidenced capabilities only (dropping Test Impact Analysis); expanding MVP with a Phase-2 capability | User confirmed the 4-capability cut as-is: Test Impact Analysis is accepted as necessary infrastructure for Root Cause Analysis to work at all, not scope creep | User |
| North-star metric: % of Root Cause Analysis verdicts matching the actual fix commit on a labeled eval set | Engineer-time-saved (harder to measure objectively); adoption/usage counts (vanity metric) | Directly falsifiable, ties into the Stage 8 LLM-eval strategy, and measures the exact claim the product makes (correct root-cause attribution) | User |
| Guardrail metrics confirmed as-is: Flaky Detection false-positive rate, LLM cost per analysis, PR-opened-to-analysis-available latency | Adding/swapping guardrails (none proposed) | User confirmed the drafted set without changes | User |
| Phase 2/3 grouping confirmed as-is (Phase 2: Coverage Intelligence, CI/CD Optimization, Dependency Analysis, Engineering Metrics, API Evolution Tracking, Regression Prediction; Phase 3: Release Risk Analysis, Release Advisor, Incident Analysis, AI Documentation, Test Generation, Architecture Insights, Knowledge Graph) | Moving a capability between phases (none proposed) | User confirmed the drafted grouping without changes; consistent with `docs/09-implementation/README.md` priority column | User |
| Positioning confirmed as IC-facing (not EM-facing) for Phase 1 | Mixed positioning (some EM-facing element even in Phase 1) | User confirmed IC-facing as-is — no persona has EM-level evidence yet, so an EM-facing element now would be unevidenced scope | User |

## Architecture Review checklist (exit criteria)

- [x] Every MVP capability traces to a specific Stage 1 persona and pain narrative —
      no capability is in MVP "because it's interesting."
- [x] MVP scope is small enough to actually ship and large enough to be non-trivial
      (a single capability is not a platform; all 17 at once is not an MVP).
- [x] The phased roadmap's ordering has explicit dependency reasoning, not just
      difficulty-based guessing.
- [x] Success metrics are falsifiable and not vanity metrics.
- [x] The interaction model (CLI/web/API/ChatOps) is decided and justified, not left
      implicit for Stage 3 to assume.
- [x] CEO and CTO have reviewed and challenged the scoring, not just the conclusion.
- [x] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Previous stage: `docs/01-problem-discovery/README.md`
- Next stage: `docs/03-architecture/README.md`
- `PROGRESS.md` entries tagged Stage 2
