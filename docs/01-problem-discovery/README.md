# Stage 1 — Problem Discovery

**Status:** `APPROVED` (2026-07-02)
**Leads:** Product Manager, CEO, System Analyst
**Reviewers:** CTO, Principal Software Engineer
**Entry criteria:** Stage 0 (Process Bootstrap) `DONE`.

## Goal

Establish, with evidence rather than assumption, that a real and specific engineering
problem exists — before any product, architecture, or technology decision is made.
This is the stage most portfolio projects skip, and skipping it is exactly why they
read as toy projects: a well-executed solution to a made-up problem is still a made-up
project. See `docs/00-process/README.md` for why this precedes Product Discovery.

## Key questions / activities

This stage is not closed until each of these has a specific, falsifiable answer — not
a plausible-sounding paragraph:

- **Who exactly** experiences this problem? Name concrete personas (e.g. "an EM
  running a 20-engineer team across 4 services," "a platform team owning CI for 200
  repos") — not "developers" or "companies."
- **What decision or action does that person currently get wrong, or fail to make
  confidently**, because the information they need is scattered across GitHub,
  GitLab, Jira, CI/CD, Prometheus, Loki, Tempo, etc.? Be specific about the moment
  this bites them (e.g. "approving a PR without knowing it touches a historically
  flaky test area," "deciding to ship a release without a clear risk signal").
- **What is the cost of getting it wrong today** — in time, in incidents, in missed
  deadlines, in engineer trust? Quantify where possible, even roughly.
- **What signal already exists but goes unused or unconnected** in their toolchain?
  (This matters: the product's core bet is *correlation and synthesis* across
  existing tools via an LLM, not new instrumentation.)
- **Why now, and why an LLM-centric approach** — what does an LLM genuinely unlock
  here (synthesis across noisy, semi-structured signals; natural-language rationale
  for a decision) versus what would just be a traditional dashboard with a chatbot
  bolted on? This distinction matters for architectural credibility later.
- **Who already solves part of this, and where do they fall short?** Survey adjacent
  categories (engineering-intelligence platforms, DORA-metrics tools, APM/observability
  vendors, CI analytics tools) honestly — not to be dismissive, but to find the actual
  gap this project targets.
- **What is explicitly out of scope?** A problem statement without a stated boundary
  isn't falsifiable.

## Deliverables

- Problem statement: specific, falsifiable, one paragraph.
- 3+ target personas with concrete pain narratives (not generic descriptions).
- Evidence/reasoning section: why this problem is real and costly, with whatever
  evidence is available (public data, first-hand experience, credible reasoning).
- Competitive/adjacent-landscape summary and the specific gap being targeted.
- Explicit non-goals list.

## Findings (final — approved 2026-07-02)

### Problem statement

Engineering teams — even small ones, not just large orgs — decide "is this safe to
merge/ship" by holding code risk, test signal, and CI/operational history in one
person's head at a time, with no synthesized signal to lean on. That judgment doesn't
scale or transfer: it depends on whoever happens to be reviewing, degrades when that
person is busy or absent, and leaves no reusable trace for next time. The tools that
exist today (dashboards, DORA metrics) show *what* happened; none of them reason
about *this specific change* and explain *why* it is or isn't safe.

### Cost of getting it wrong (approximate — reasoned, not measured)

- Every time a failing test requires manual code-tracing to find the real failure
  point (Persona #1), that's engineer time spent on archaeology instead of the fix
  itself — repeated per incident, with no accumulated shortcut over time.
- Every chronic-vs-one-off flaky pipeline misjudgment (Persona #2) means remediation
  effort is spent on the wrong pipeline, while the real chronic offender keeps
  costing CI time and eroding trust in "red" meaning something.
- Every ad hoc, single-person code-quality gate (Persona #3) is a single point of
  failure: it doesn't transfer if that person is unavailable, doesn't scale past
  what one person can personally review, and leaves no record of *why* a merge was
  or wasn't blocked for the next similar case.

### Personas

**1. SDET/QA Engineer triaging a failing test — evidence: first-hand (user, small
team context).**
Pain, specifically: when a test fails, even with solid test logging in place,
determining (a) whether it's a real regression or a known flake, and (b) *where in
the code* it actually originates, requires manually tracing through the codebase's
class/method structure. Good logs reduce noise but do not shortcut this step — the
gap isn't "we lack data," it's "connecting the failure signal to the actual
responsible code path is manual archaeology every time," independent of log quality.
This maps most directly to **Root Cause Analysis** (and secondarily **Flaky
Detection**).

**2. Platform/CI-owning engineer distinguishing chronic flakiness from a one-off
blip — evidence: first-hand (user, confirmed as accurate to real experience).**
Pain, specifically: without a history-aware view, a failing pipeline looks the same
whether it's a genuinely unstable area or a random blip — remediation effort gets
prioritized on guesswork. Notably, this pain doesn't require a large team/org to be
real — it requires enough CI run *volume* over time, which even a small team
accumulates. This maps most directly to **Flaky Detection** and **CI/CD
Optimization**.

**3. Small-team release decision-maker — evidence: first-hand (user, confirmed
2026-07-02).**
Whoever, in a small team, ends up being the one who actually decides "is it OK to
ship right now" — formal EM title or not. Confirmed by two real, separate incidents
at the user's company where the director blocked a merge to prod: once over
poor UX/UI (a *product* judgment call — out of scope, see Non-goals), and once over
poorly-written code (an *engineering* judgment call). The engineering case is the
persona's real pain: that gate is entirely manual, lives in one person's read of a
diff, and doesn't scale or transfer if that person is unavailable or simply misses
something — there is no synthesized signal backing the call, only individual
judgment. This maps to **PR Analysis** and **Architecture Insights**.

### Non-goals (draft)

- Not a replacement for Prometheus/Grafana/Datadog — these are data sources, not
  competitors.
- Not a project-management tool — does not replace Jira.
- Not an auto-merge/auto-block system — the platform advises; a human keeps the
  final call. (Automating the decision itself would be a materially different, far
  riskier product with its own trust/liability problem — explicitly out of scope.)
- **Not a product/UX-readiness judgment tool.** Real example: the user's director
  once blocked a prod merge purely over UX/UI quality — a legitimate call, but a
  product judgment, not an engineering-risk one. Sibyl reasons about code, tests,
  CI, and operational signal; it has no opinion on whether a feature is good enough
  for users. This is a deliberate boundary, not an oversight — conflating the two
  would blur the product into something no longer defensible as "engineering
  intelligence."

### Why an LLM, specifically (not just a dashboard)

All three confirmed problems share the same shape: the *inputs* already exist
(logs, test history, CI history, the diff itself) — what's missing is the step that
turns them into a specific, explained verdict about *this* change. A dashboard can
show "this test failed 4 times this month" or "this file changed 200 times"; it
cannot say "this failure is almost certainly caused by the change to `OrderValidator`
three commits ago, here's the call path" or "this merge looks like the same pattern
that caused last month's blocked PR." That synthesis step — correlating
heterogeneous, semi-structured signal into a specific natural-language explanation —
is what an LLM adds that a metrics pipeline structurally cannot. This is also why
Sibyl is architected with the LLM behind a reasoning port fed by *pre-correlated*
context (Stage 3), not just handed a chat window over raw data.

### Competitive/adjacent landscape (draft)

LinearB, Sleuth, Faros AI, DX (getdx.com), Waydev, Cortex, Swarmia — broadly: DORA
metrics and productivity dashboards. None of these do causal/predictive reasoning
about a *specific* change via an LLM (root-causing a specific failure, or narrating
*why* a specific release is risky) — they report metrics, they don't synthesize an
explanation. That gap is this project's target.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| Adopt the 3-persona set: SDET root-cause tracing, Platform/CI flaky-vs-blip, small-team ad hoc release gate | Original draft persona #3 ("EM over multiple squads") | User had no first-hand basis for that scale; reframing to a small-team-shaped role let it be evidenced instead of assumed | Product Manager / user |
| Treat "poor UX/UI" merge-block and "poorly-written code" merge-block as two different problem classes | Treating the director's ad hoc gating as one undifferentiated phenomenon | Would blur product judgment into engineering-risk judgment and contradict the non-goals boundary | Product Manager / user |
| Scope Sibyl strictly to engineering-risk signal, explicitly excluding product/UX readiness | Broadening scope to also advise on product/UX readiness | No evidence base for it, and it would dilute "engineering intelligence" into a vaguer, less defensible product | CEO / user |
| LLM's role is framed as synthesis-over-pre-correlated-context, not chat-over-raw-data | A conversational/chatbot interface directly over raw logs/metrics | Doesn't structurally solve the actual gap (connecting heterogeneous signal to a specific verdict); also pre-empts the Stage 3 architecture decision to keep the LLM behind a reasoning port | CTO |

## Architecture Review checklist (exit criteria)

- [x] Problem statement is specific and falsifiable — someone could disagree with it
      on factual grounds, not just taste.
- [x] At least 3 named personas, each with a concrete pain narrative tied to a real
      moment/decision, not a generic job description.
- [x] The cost of the problem is stated in concrete terms (time/risk/money), even if
      approximate.
- [x] The "why an LLM" argument is explicit and distinguishes this from a plain
      dashboard.
- [x] A non-goals list exists and is specific enough to actually exclude things.
- [x] CTO and Principal SWE have reviewed and challenged the evidence, not just
      rubber-stamped it.
- [x] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Process rationale: `docs/00-process/README.md`
- Next stage: `docs/02-product-discovery/README.md`
- `PROGRESS.md` entries tagged Stage 1
