# Stage 8 — Testing Strategy

**Status:** `APPROVED` (2026-07-02)
**Leads:** Senior SDET, Senior Python Developer
**Reviewers:** Principal Software Engineer, Senior Security Engineer
**Entry criteria:** Stage 7 (Infrastructure) `APPROVED`.

## Goal

Define the test pyramid for this specific system — including the parts a generic
testing-strategy template won't cover, like LLM output evaluation and this platform's
own flaky-test tolerance — as a contract that Stage 9 code is written to satisfy, not
retrofitted after the fact.

## Key questions / activities

- **Unit tests**: per bounded context, fast and isolated via the hexagonal
  ports/adapters from Stage 3 — domain logic tested without a database or network.
- **Contract tests**: for every external adapter (GitHub, GitLab, Jira, Confluence,
  CI/CD, Docker/Kubernetes API, Prometheus/Grafana/Loki/Tempo, LLM provider) — since
  this platform's entire value is its integration surface, that surface needs
  contract-level confidence, not just mocked unit tests.
- **Integration tests**: against real Postgres/Kafka/Redis via testcontainers, not
  mocks — validating the outbox/event-publishing correctness from Stage 4.
- **End-to-end tests**: Playwright against the actual dashboard/API, covering the
  Stage 2 core user journeys.
- **LLM-specific testing strategy**: this is the part most projects get wrong.
  Deterministic evals against golden datasets, regression detection for prompt/model
  changes, cost and latency budget tests, and an explicit policy for how much
  output variance is tolerated before a test is considered failing. LLM tests must be
  reproducible, not vibes-based "looks reasonable" checks.
- **This platform's own flaky-test policy**: since Flaky Detection is a product
  capability, the project's own test suite is held to zero tolerance for flakiness —
  define what "flaky" means operationally and what happens when one is found (quarantine
  + ticket, not silent retry-until-green).
- **Coverage targets and enforcement**: what's measured, what threshold gates CI, and
  for which parts of the codebase (domain logic vs. adapters vs. glue code likely have
  different realistic targets — justify them, don't pick 100% by default).
- **Load/performance testing approach**: tooling and scenarios, feeding Stage 10.
- **Definition of Done**: the checklist every future PR must satisfy before merge.

## Deliverables

- Testing strategy document with the test pyramid explicitly diagrammed.
- LLM evaluation framework design (golden sets, eval harness, regression gating).
- Coverage policy and CI enforcement configuration.
- This project's own flaky-test policy.
- Definition of Done checklist.

## Findings (final — approved 2026-07-02)

### Test pyramid

| Layer | Scope | Tooling | Runs in CI (Stage 7) |
|---|---|---|---|
| Unit | Domain logic per bounded context, isolated via ports/adapters — no DB, no network, no LLM | Pytest, `unittest.mock` / `pytest-mock` | `test` job, every PR |
| Contract | Every external adapter's request/response shape: GitHub webhook parsing, GitHub Checks API calls, `ReasoningPort` (against recorded fixtures, never a live LLM call), Postgres repository implementations against their port interface | Pytest + `responses`/`httpx-mock` for HTTP adapters, `testcontainers` for Postgres-backed repository contracts | `test` job, every PR |
| Integration | Real Postgres + Kafka + Redis via `testcontainers` — the actual outbox → relay → Kafka → consumer → read-model flow, unmocked | Pytest + `testcontainers` | `test` job, every PR (already has Postgres/Redis services wired in `ci.yml`; Kafka service added when Stage 9 needs it) |
| End-to-end (MVP-redefined) | Full webhook → analysis → GitHub Check/comment flow, against a sandboxed GitHub App test installation (or a fully mocked GitHub API for CI) | Pytest + `httpx`/recorded fixtures | Scheduled/nightly, not required-per-PR (talks to external-ish surfaces even when mocked, slower than the other tiers) |

**Playwright is not used in MVP.** It's pinned in the tech stack for a real
reason — Stage 2 explicitly deferred any web dashboard to Phase 2, and Playwright
tests a browser. Forcing it into MVP (e.g., driving a browser against the bare API
docs page) would be using a tool because it's on the list, not because it's the
right tool for what exists. **"E2E" for MVP is redefined** to mean the full
webhook-to-GitHub-comment flow above — genuinely end-to-end for a system with no
UI yet. Playwright is picked back up in Phase 2 once the dashboard (deferred in
Stage 2) actually exists to test.

### LLM evaluation framework

Directly resolves the open question from ADR-0005 ("how is determinism/evaluation
possible given LLM non-determinism"):

- **Unit and contract tests never call a real LLM.** `ReasoningPort` is replaced by
  a `FakeReasoningPort` returning canned, schema-valid responses — this is most of
  the test suite, fully deterministic, fast, free.
- **The real adapter is validated separately**, against a curated **golden
  dataset** of `(correlated context, expected outcome)` pairs drawn from real or
  realistic PR/failure examples. Scoring is on **structured fields**, not
  free-text exact-match: does the risk `score` fall within an acceptable band of
  the labeled outcome, does `suspected_file_path` match the actual fix location,
  etc. — the same shape as the Stage 2 north-star metric, just run as a gate
  instead of a live product metric.
- **This eval job is scheduled, not per-PR** — it exercises the real provider
  (cost, latency, non-determinism all apply), and is explicitly the gate for any
  prompt or model-version change, not for every commit. A prompt/model change that
  regresses the golden-set score is treated as a failing check on *that* PR.
- Cost and latency budget tests assert against the Stage 2 guardrail metrics
  (LLM cost per analysis, PR-opened-to-analysis-available latency) using the fake
  port's recorded historical costs from the real adapter's telemetry, not live
  calls in the fast test suite.

### Coverage targets (justified per category, not a flat 100%)

| Category | Target | Why |
|---|---|---|
| Domain logic (per bounded context) | 90%+ | Pure logic, cheap to test in isolation, highest value to protect — this is where the actual business rules live |
| Adapters (GitHub, Kafka, Postgres, LLM) | 70–80% | Some paths only exercise meaningfully via contract/integration tests, not pure unit coverage; error-handling edge cases are harder to synthesize exhaustively |
| Glue/wiring (DI, app startup, config loading) | 50% | Mostly declarative, low behavioral risk, low value in chasing higher numbers here |
| **Overall CI gate** | **80%**, `pytest --cov --cov-fail-under=80` | Matches the `test` job already wired in `.github/workflows/ci.yml` (Stage 7) — this stage supplies the threshold that job was left open-ended |

### This project's own flaky-test policy

**Definition:** a test is flaky if it produces different outcomes across runs with
identical code, inputs, and environment.

**Detection:** CI automatically reruns a failed test up to 2 times
(`pytest-rerunfailures`) — *only* to distinguish a transient CI-infra blip (e.g., a
testcontainer race) from a real failure. If a test passes on rerun, it does **not**
silently go green and get forgotten — it's flagged and logged as a suspected-flaky
incident.

**Response:** a test flagged twice within any 14-day window is quarantined
(`@pytest.mark.quarantine`) — still run and reported, but excluded from the
required-check gate — with a mandatory 14-day fix SLA before it's either fixed or
permanently removed. Quarantine is visible (a dashboard-free "list quarantined
tests" report), never a silent skip.

**The obvious dogfooding opportunity, worth calling out explicitly:** Flaky
Detection is an MVP capability, not a Phase 2 one. Once Stage 9 ships it, pointing
Sibyl at its own repository's own CI history is a genuine, concrete validation of
the product — unlike the API Evolution Tracking dogfooding idea (Phase 2, noted
but not actionable yet in Stage 4), this one is real and available as soon as MVP
is live.

### Definition of Done (gates every Stage 9 PR)

- [ ] No comments in the code (standing project rule).
- [ ] Unit tests added/updated for changed domain logic; contract tests
      added/updated if an adapter's external contract changed.
- [ ] Coverage gate passes for the affected tier (domain/adapter/glue).
- [ ] No new flaky test introduced (no rerun-confirmation triggered in CI).
- [ ] Observability touch points match what the relevant Stage 6 diagram specifies
      for this flow (span, metric, structured log).
- [ ] `ЖУРНАЛ_РАЗРАБОТКИ.md` updated with what/why for this change.
- [ ] `PROGRESS.md` updated if the change represents a stage/decision change.
- [ ] Security review if the change touches auth, secrets, or webhook signature
      verification (per Stage 7's secrets-handling checklist).
- [ ] No secret committed, in code or in a container image layer.

### Load/performance testing (tooling only — scenarios detailed at Stage 10)

**k6** for API load generation, run against the ADR-0007 scalability targets (50
repos, 200 PRs/day, p95 < 300ms). Not run in per-PR CI — a Stage 10 activity once
there's a real deployment to point it at.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| Redefine "E2E" for MVP as the full webhook→analysis→GitHub-comment flow; defer Playwright to Phase 2 | Forcing Playwright against the bare API/docs now | Nothing browser-based exists in MVP (Stage 2 deferred the dashboard) — using Playwright now would be tool-first, not need-first | Senior SDET / user |
| LLM eval golden-set job runs scheduled/on-prompt-change, not per-PR; per-PR tests use a fake `ReasoningPort` | Calling the real LLM provider in every CI run | Cost, latency, and non-determinism make per-PR live LLM calls both expensive and unreliable as a gate | Senior AI Engineer |
| Coverage gated at 80% overall with per-category targets (90/75/50) rather than a flat 100% | Flat 100% coverage requirement | 100% coverage is a vanity metric that pushes low-value tests on glue code; per-category targets reflect actual risk | Senior SDET |
| Flaky tests quarantined with a 14-day fix SLA, not silently retried forever | Auto-retry-until-green with no visibility or SLA | Silent retries are exactly the "trust erosion" problem the product itself (Flaky Detection) exists to solve — the project can't hold a double standard | Senior SDET |

## Architecture Review checklist (exit criteria)

- [x] Every test layer (unit/contract/integration/e2e) has a named owner tool and a
      CI pipeline stage from Stage 7 to run in.
- [x] The LLM eval approach is deterministic and reproducible — golden sets and
      explicit pass/fail criteria, not subjective review.
- [x] Coverage targets are justified per code category, with CI enforcement wired.
- [x] The project's own flaky-test policy is defined and specific (definition,
      detection, response).
- [x] A ratified Definition of Done checklist exists and will gate every Stage 9 PR.
- [x] Principal SWE and Senior Security Engineer have reviewed, with security
      specifically checking that security-relevant paths (auth, secrets, webhook
      signature verification) have explicit test coverage requirements.
- [x] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Previous stage: `docs/07-infrastructure/README.md`
- Next stage: `docs/09-implementation/README.md`
- `PROGRESS.md` entries tagged Stage 8
