# Operations Strategy — Development, Debugging, CI/CD, Launch

**Status:** Living document (not stage-gated itself — see "Why this document
exists" below)
**Owner roles:** Engineering Manager (roadmap sequencing), Staff Platform
Engineer / Senior DevOps (CI/CD & launch), Senior SDET (debugging practice),
Open Source Maintainer (publication readiness)
**Last updated:** 2026-07-02

## Why this document exists

This project's process (`docs/00-process/README.md`) maps every deliverable to
one of 10 numbered stages, each closed by an Architecture Review gate. That
discipline is correct for *design* decisions — but "how do we keep developing,
debugging, shipping, and eventually launching this" is a cross-cutting
operational concern that doesn't belong to any single stage:

- Stage 7 (Infrastructure) froze the deployment topology, CI/CD pipeline
  *shape*, and observability stack — but not how to actually operate them
  day-to-day, or the concrete sequence of steps to go from "code on a laptop"
  to "running in production."
- Stage 8 (Testing Strategy) froze the test pyramid, coverage gates, and the
  flaky-test *policy* — but not a debugging playbook for using that
  infrastructure when something actually breaks.
- Stage 9 (Implementation) is where capabilities get built, but its own doc
  is a dependency/priority catalog, not a sequencing narrative for what
  remains.
- Stage 10 (Optimization) is explicitly post-launch, evidence-driven
  hardening — it assumes the system is already live with real usage data. It
  is not a "how do we launch" plan.

This document does not re-decide anything Stage 7/8 already froze — it
references those decisions and adds the actionable, forward-looking layer on
top: sequencing, runbooks, and concrete next steps. Per the documentation
policy addendum below, this is a new artifact class: a living, top-level
strategy doc, updated as Stage 9/10 progress, not itself subject to an
Architecture Review gate (there is no fixed "content" for it to be reviewed
against — it is deliberately meant to change).

## 1. Further development strategy

### Current snapshot (see `PROGRESS.md` `CURRENT STATE` for the live version)

All 4 confirmed-MVP capabilities are `APPROVED` (9.0, 9.1, 9.2, 9.3, 9.9), plus
the first four Phase 2 capabilities (9.5 CI/CD Optimization, 9.4 Coverage
Intelligence, 9.6 Dependency Analysis, 9.8 API Evolution Tracking). 9
sub-stages remain.

### Remaining Phase 2 (9.7) — sequencing recommendation

| Sub-stage | New integration cost | Recommended order | Why |
|---|---|---|---|
| 9.7 Engineering Metrics | High — needs deployment events, not currently ingested at all (no deployment webhook exists) | Defer until a real deploy pipeline exists to source events from (see §4) | DORA-style metrics need deployment frequency/lead-time data; building this before there's a real CI/CD release flow to measure would mean synthesizing fake deployment events, which defeats the point |

9.7 is the only Phase 2 sub-stage left, and it's the one this table has
recommended deferring since it first appeared — not because it's low
priority, but because building it now would mean faking the exact data it's
meant to measure. Once this is the *only* thing standing between Phase 2 and
Phase 3, the real question becomes "start Phase 3" vs. "revisit whether 9.7's
blocking condition (a real deploy pipeline) is now closer than it was" — a
call for the user, not a scheduling default. Every sub-stage decision
documented in `PROGRESS.md` so far (9.5, 9.4, 9.6, 9.8, each over their
remaining Phase 2 siblings) picked lowest-new-integration-cost first, or —
for 9.6 — the capability that unblocks the most other work; this table
continues that reasoning explicitly.

### Phase 3 (9.10–9.17)

Not evaluated in detail yet — per `docs/09-implementation/README.md`, Phase 3
is built only after all Phase 2 sub-stages close. 9.17 (Knowledge Graph)
depends effectively on all prior capabilities and is correctly last.

### Entry criteria for Stage 10 (Optimization)

Per `docs/10-optimization/README.md`, Stage 10 begins once there is **real
production usage to generate evidence from** — not once every sub-stage is
built. In practice this means Stage 10 work can interleave with Phase 2/3
sub-stages once this project is actually deployed and has real traffic (see
§4, Launch strategy) — it does not have to wait for all 17 capabilities.

### Standing per-sub-stage rigor (unchanged)

Every remaining sub-stage follows the same loop used for
9.0–9.5/9.4/9.6/9.8/9.9: confirm against frozen Stage 3–8 contracts → design
(surface any real gap as an addendum, as happened in
9.2/9.3/9.5/9.4/9.6/9.8/9.9, never silently) → implement → test → document
(`docs/09-implementation/9.NN-<slug>/README.md` from the template) → update
`PROGRESS.md` and `ЖУРНАЛ_РАЗРАБОТКИ.md`.

### Open items requiring an explicit decision (tracked here so they aren't lost)

- **License** — undecided since Stage 0. Doesn't block Stage 1–9 work, but
  does block launch (§4) and public repo publication. Needs a decision before
  this repo is pushed anywhere public.
- **`pr_analysis.pr_risk_assessment.llm_tokens_used`/`llm_latency_ms`** —
  frozen in the Stage 4 ERD, never implemented in 9.1's shipped code,
  discovered while building 9.9's equivalent column. Needs: backfill via a
  new migration + code change, or amend the Stage 4 doc to match shipped
  reality. Neither has happened yet.

## 2. Debugging strategy

### Local development loop

1. `docker compose up -d` — Postgres (5 schemas), Redis, Kafka (KRaft),
   full observability stack. `docker compose config --quiet` validates the
   file if something looks wrong.
2. Run the API/worker locally against that stack (`DATABASE_URL`,
   `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS` pointed at `localhost`).
3. `DOCKER_HOST=unix:///Users/qa-engeneer/.docker/run/docker.sock uv run
   pytest` for the integration/contract tiers, which spin up their own
   throwaway `testcontainers` — independent of the docker-compose stack above
   (don't confuse the two; a testcontainers failure isn't a docker-compose
   problem and vice versa).
4. `uv run ruff check . --fix && uv run mypy src tests` before any commit —
   both must be clean; this is the fastest feedback loop, always run before
   the full test suite.

### Observability-driven debugging (using the Stage 7 stack for real)

The stack exists (OTel Collector → Prometheus/Loki/Tempo, Grafana
pre-provisioned) but nothing yet emits real traces/metrics beyond structured
logs, since Stage 9 hasn't wired OpenTelemetry spans (every sub-stage so far
has deferred this explicitly — see each sub-stage doc's Observability
section). Until that's wired:

- **Today**, debugging means reading structured JSON logs (`worker.*`
  events already emitted per handler — e.g. `worker.root_cause_analysis.ci_run_processed`)
  and querying Postgres directly (`docker exec sibyl-postgres-1 psql -U sibyl
  -d sibyl`) to inspect table state per bounded-context schema.
- **Once spans are wired** (a real gap to close, not yet scheduled to a
  specific sub-stage — candidate for whichever sub-stage next touches the
  worker consumer groups, or a dedicated cross-cutting pass), Tempo becomes
  the tool for "why did this specific correlation take 4 seconds" and
  Grafana dashboards answer "is `root_cause.partial_context_total` climbing."
  Don't build dashboards before there are metrics to show — same
  evidence-before-speculation principle as Stage 10.

### Common failure modes, per bounded context (a living runbook)

- **Ingestion**: webhook signature failures (401) almost always mean a
  misconfigured `GITHUB_WEBHOOK_SECRET`, not an attack — check `.env` first.
  Malformed-payload 400s are expected and GitHub won't retry them; check the
  `ingestion.malformed_total` log line for which field was missing.
- **Test Intelligence**: if `test-intelligence.impact-computed` never fires
  for a PR, check both halves of the bidirectional correlation exist —
  `pr_changed_files_projection` and at least one `test_run` for the *same*
  `commit_sha`. A stale/rebased PR head is the most common reason one half is
  missing.
- **PR Analysis / Root Cause Analysis**: `explanation_unavailable=true` on a
  result means the LLM fallback fired — check `llm.timeout_total` /
  `llm.provider_error_total` /`llm.schema_validation_failed_total` structured
  log lines (Stage 6 §6) to tell which failure mode, rather than assuming
  "the LLM is down."
- **Root Cause Analysis correlation stuck**: per the 9.9 design notes, a
  hypothesis never computing means one of the three inputs
  (`failure_event`/`pr_context_projection`/`test_impact_projection`) is
  missing — query all three directly for the `(repository, commit_sha)` in
  question rather than guessing; there is no timeout to "wait out."
- **Alembic migrations**: if autogenerate proposes recreating tables that
  already exist, this was a real bug (fixed 2026-07-02, see the Stage 4
  addendum and 9.5's sub-stage doc) — `include_schemas=True` was missing
  from `env.py`. If a *new* schema-comparison anomaly appears, check that
  fix is still in place before assuming a new bug.

### Flaky-test quarantine, in practice

Per Stage 8: a test flagged flaky twice within 14 days gets
`@pytest.mark.quarantine` and a mandatory 14-day fix SLA — visible in CI
output, never a silent skip. As of this writing, no test has ever needed
quarantine (163/163 passing, no reruns observed) — this section exists so
the *process* is documented before it's ever needed under time pressure.

## 3. CI/CD activation & release strategy

### Current state — verified green on GitHub Actions (2026-07-03)

The repository is pushed to `Boss-Of-Gym/Sibyl` on GitHub (`origin`, public).
`.github/workflows/ci.yml`'s 5 stages (lint → typecheck → test → security-scan
→ build) have now **actually executed against real code in GitHub Actions**,
not just locally via `uv run ...`. The first real run (commit `f29bfe3`)
surfaced three genuine gaps that local validation had never exercised —
confirming the OPERATIONS_STRATEGY prediction that a hosted-runner run would
differ from local dev, though not in the dimension expected (testcontainers
themselves worked fine on the first try — `lint` and `test` passed
immediately):
- `typecheck` ran `uv run mypy .` (whole repo) in CI, but only `mypy src
  tests` had ever been run locally — `alembic/env.py`'s `include_object`
  callback used loose `object`/`str` parameter types that strict mypy
  rejects under Alembic's real signature. Fixed by typing it against
  `SchemaItem`/`Literal[...]` to match Alembic's actual stub.
- `security-scan` failed at "Set up job" itself, before any step (even
  checkout) ran — `aquasecurity/trivy-action@0.24.0` is not a resolvable tag
  (current releases use a `v`-prefix). Fixed to `@v0.36.0`.
- `pip-audit` was invoked via `uv run pip-audit` but was never declared as a
  project dependency anywhere — would have failed as soon as the job-setup
  issue above was fixed. Added `pip-audit` to the `dev` dependency group.

All three were real, previously-latent gaps between "validated locally" and
"what CI actually runs" — none were introduced by this fix, only exposed by
finally running the pipeline for real. Commit `b3f93a5` (run `28671697831`)
is fully green: `lint`, `typecheck`, `test`, `security-scan`, `build` all
`success`.

### Steps to activate CI for real

1. ~~Decide the license (§4 blocks on this too — do it once, not twice).~~
   Still open — not resolved by this activation work; §4 still blocks on it.
2. ~~Create the GitHub repository, push the existing local history.~~ Done
   2026-07-03 (`Boss-Of-Gym/Sibyl`, public).
3. ~~Confirm the 5-stage pipeline goes green on the first push.~~ Done
   2026-07-03, after fixing the three gaps above — see "Current state" above.
   Docker-in-Docker for `testcontainers` worked on GitHub-hosted runners
   without any changes needed, resolving that specific risk.
4. Add branch protection on `main`: require the `lint`, `typecheck`, `test`,
   and `security-scan` jobs (not `build`, which only runs on `push` to `main`
   itself) as required status checks before merge; require PR review. **Not
   yet done** — a repo-settings change, visible/consequential enough to
   confirm with the user explicitly before applying, not to bundle into a
   code-fix session.
5. Add a `Dockerfile` for the `api` and `worker` images (Stage 9.0 scope).
   **Confirmed still missing** — checked directly during this activation
   work (no `Dockerfile` anywhere in the repo root). The `build` job's
   `if: hashFiles('Dockerfile') != ''` guard means it currently reports
   `success` by skipping its one real step entirely, not by actually
   building anything — a gap in 9.0's Definition of Done, not a new one.

### Versioning & release strategy (not yet decided — proposed here)

No versioning scheme is frozen anywhere in Stages 1–9. Proposed, for
confirmation:
- **SemVer** (`MAJOR.MINOR.PATCH`), git-tag-driven (`v0.1.0` for first
  deployable release).
- **`0.x` until Stage 10 closes** — this project is explicitly pre-hardening
  until then; a `1.0.0` tag before Stage 10's exit checklist is satisfied
  would overstate production-readiness.
- **Container image tags** = git tag, published to GHCR on tag push (the
  Helm chart's `values.yaml` already references
  `ghcr.io/sibyl-platform/sibyl-api`/`sibyl-worker` at `0.1.0-dev` — this
  needs a real publish step added to CI, not yet built).
- **`CHANGELOG.md`** — does not exist yet; per this project's own "argue with
  weak proposals" discipline: a hand-maintained changelog for a project this
  early is likely lower-value than deriving release notes from `PROGRESS.md`'s
  existing dated log (which is already more detailed and honest about
  trade-offs than a typical changelog) — recommend *not* building a separate
  changelog unless the audience genuinely needs one (e.g., external API
  consumers, which don't exist yet).

### Environment promotion flow (proposed, not yet built)

Given Stage 7's environment table (local → staging → production) and no CI/CD
deployment automation exists yet:
- **Trunk-based**: PRs merge to `main` after required checks pass.
- **`main` → staging**: auto-deploy on merge (once a staging cluster exists —
  see §4). Low risk, fast feedback, matches this project's "single developer,
  modular monolith" scale (ADR-0001's reasoning applied here too — a heavier
  GitOps/multi-environment-promotion pipeline is unearned complexity at this
  scale).
- **staging → production**: manual promotion (re-tag the already-built
  image, apply to the production Helm release) until Stage 10 establishes
  enough confidence/evidence to automate it. Automating production deploys
  before there's production traffic to validate against would be the same
  "evidence before speculation" mistake Stage 10 explicitly avoids elsewhere.

## 4. Launch strategy (path to production)

### Pre-launch checklist

- [ ] **License decision** (blocks public publication — see Stage 0's open
      blocker, still unresolved).
- [ ] GitHub App registration (real GitHub App, not the fixture/mock used in
      tests) — needed before any real installation can authenticate.
- [ ] Real secrets provisioned out-of-band into a Kubernetes `Secret` named
      `sibyl-secrets` (per Stage 7's frozen secrets policy) — GitHub App
      private key, webhook secret, OAuth client secret, LLM provider API key,
      JWT signing key, DB/Redis credentials.
- [ ] Repository publication polish (much of this is already drafted, just
      not yet applied): root `README.md`'s existing "Name & repository
      description" section already has a ready-to-use GitHub About
      description, topics list, and social-preview text — apply them when
      the repo is actually made public, don't re-draft them.
- [ ] CI activated and green (§3).
- [ ] `Dockerfile`s exist and `build` job produces real images.

### Staging rollout

1. Provision a real (or local `kind`/`minikube`) Kubernetes cluster.
2. `helm install sibyl deploy/helm/sibyl -f values-staging.yaml` (a
   staging-specific values overlay doesn't exist yet — create one; don't
   reuse the MVP `values.yaml` verbatim since its image tags/ingress host
   are placeholders).
3. Point the real GitHub App's webhook at the staging ingress host.
4. Install the GitHub App on one real test-owned repository (per Stage 7's
   environment table: "real GitHub App test installation").
5. Validate the full webhook → analysis → GitHub Check/comment flow
   end-to-end against real GitHub, not mocked — this is genuinely the first
   time that happens; every test so far uses `httpx.MockTransport` or fake
   reasoning ports by design (correctly, for fast/deterministic CI — but it
   means the real integration has never been exercised).

### Production rollout

Same Helm chart, production `values.yaml` overlay, real domain
(`api.sibyl.dev` per the current placeholder, or the user's actual domain),
real cert-manager-issued TLS. Gate on: staging validation clean for some
observation period (a specific duration isn't decided — propose at least one
full day of real PR/CI activity on the staging test repo before promoting,
adjustable with evidence once Stage 10 has real data to reason from).

### Rollback plan

- `helm rollback sibyl <previous-revision>` — standard Helm rollback,
  already available for free from using Helm at all; no custom tooling
  needed at this scale.
- Database migrations should remain backward-compatible one version back
  (per Stage 4's expand-contract pattern) specifically so a Helm rollback
  doesn't require a matching migration rollback in the common case.
- No automated rollback-on-error-rate exists yet (would need the
  metrics/alerting Stage 10 is responsible for establishing with real data)
  — manual rollback only until then.

### Go/no-go criteria

Launch (first production deploy) does **not** require Stage 10 to be
complete — Stage 10 is evidence-driven hardening that needs production
traffic to exist first, so some amount of "launch before fully hardened" is
inherent to this project's own stage ordering. Launch *does* require: the
pre-launch checklist above complete, staging validation clean, and rollback
plan understood by whoever is operating it. This is a lower bar than Stage
10's own exit checklist, intentionally — that checklist is for calling the
platform *hardened*, not for calling it *launchable*.

## Related docs

- `docs/07-infrastructure/README.md` — frozen deployment topology, CI/CD
  pipeline shape, secrets policy, environment table (this document extends,
  never contradicts, that one).
- `docs/08-testing-strategy/README.md` — frozen test pyramid, LLM eval
  approach, flaky-test policy, Definition of Done.
- `docs/09-implementation/README.md` — the sub-stage dependency/priority
  catalog this document's §1 sequences into an actual recommendation.
- `docs/10-optimization/README.md` — the evidence-driven hardening stage this
  document's launch plan feeds into.
- `PROGRESS.md` — the authoritative, dated log; this document is
  forward-looking strategy, `PROGRESS.md` is the backward-looking record of
  what actually happened.
