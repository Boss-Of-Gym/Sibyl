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
four of five Phase 2 capabilities (9.5 CI/CD Optimization, 9.4 Coverage
Intelligence, 9.6 Dependency Analysis, 9.8 API Evolution Tracking). Repo is
public, CI verified green (2026-07-03). 9 Stage 9 sub-stages remain, plus
Stage 10 in full.

### Full completion roadmap (recorded 2026-07-03, per-role phased plan)

This is the standing plan for everything between here and a genuinely
complete project — kept here (not only in chat) so any future session can
pick it up without re-deriving it. Re-validate against `PROGRESS.md`
`CURRENT STATE` each time before acting on it — this section describes intent
and sequencing, `PROGRESS.md` is what actually happened.

**Phase 0 — Documentation hygiene (Tech Writer / Engineering Manager).** ✅
Done 2026-07-07: `docs/09-implementation/README.md`'s status header synced
`NOT_STARTED` → `IN_PROGRESS`; audited every other stage README's status
header, no further drift found.

**Phase 1 — Close known Definition-of-Done gaps before new feature work**
(higher priority than more capabilities — these make existing claims honest):
1. ✅ Done 2026-07-07: `pr_analysis.pr_risk_assessment.llm_tokens_used`/
   `llm_latency_ms` backfilled. Investigation before implementing corrected
   the premise — the columns didn't exist at all (not "existed but
   unpopulated"), and `root_cause_analysis` (the presumed reference
   implementation) turned out to be missing `llm_latency_ms` too. Both fixed
   together via one shared mechanism: `platform/reasoning_guard.guarded_llm_call`
   now measures latency once, generically, for both LLM-calling contexts. See
   `docs/09-implementation/9.1-pr-analysis/README.md` and
   `docs/09-implementation/9.9-root-cause-analysis/README.md` Changelogs, and
   the Stage 4 addendum in `docs/04-database/README.md`.
2. Wire real OpenTelemetry spans/metrics into the worker consumer groups and
   API handlers (Staff Platform Engineer) — every sub-stage so far has
   deferred this explicitly; today the full Prometheus/Loki/Tempo/Grafana
   stack is provisioned but emits nothing beyond structured logs. This is the
   single biggest gap between "observability" as a claimed architectural
   quality (`MASTER_PROMPT.md` §9) and what's actually demonstrated.
3. Curate the golden-set eval dataset and wire the scheduled LLM-eval job
   (Senior AI Engineer, Senior SDET) — a Stage 8 decision never executed.
4. ✅ Done 2026-07-07: `Dockerfile` added (multi-stage, `api`/`worker` targets
   via `--target`), `.dockerignore` added, both images built and verified
   locally. CI's `build` job will now build real images instead of skipping
   its one step via the `hashFiles('Dockerfile')` guard.
5. ✅ Done 2026-07-07: License decided — Apache-2.0 (`LICENSE`,
   `pyproject.toml`, root `README.md` updated).
6. ✅ Done 2026-07-07: Branch protection applied to `main` — required status
   checks (`lint`, `typecheck`, `test`, `security-scan`), `strict=true`,
   `enforce_admins=false`, no required PR review (confirmed with the user:
   this is a solo-maintainer repo with no second reviewer, so requiring PR
   approval would have blocked direct pushes without unblocking anything in
   return).

Also discovered during Phase 1 (Dockerfile work), **not yet fixed** — a real
gap for a future Phase 1 item or the OpenTelemetry pass above: `worker.py`
has no HTTP server at all, but `deploy/helm/sibyl/templates/worker-deployment.yaml`
configures `livenessProbe`/`readinessProbe` as `httpGet` checks against
`metricsPort` (8001). This was flagged as a forward-reference risk back at
Stage 7's close ("worth checking at Stage 9.0 that the paths match exactly
what gets built") but never verified until now. Deploying the worker to real
Kubernetes today would fail its probes immediately. Natural to fold into the
OpenTelemetry pass (item 2) since a `/metrics` endpoint needs the same kind
of lightweight HTTP server the worker currently lacks entirely.

**Phase 2 — Phase 3 capabilities with no outstanding dependency**, buildable
now in any order (Senior Python Developer/SDET build, Principal Software
Engineer + Senior Security Engineer review, user sign-off — same loop as
every prior sub-stage):
- 9.10 Regression Prediction (needs 9.2, 9.9 — both `APPROVED`)
- 9.14 AI Documentation (needs 9.0, 9.1 — both `APPROVED`)
- 9.15 Test Generation (needs 9.2, 9.4 — both `APPROVED`)
- 9.16 Architecture Insights (needs 9.6, 9.8 — both `APPROVED`)

**Phase 3 — 9.7 Engineering Metrics** (Engineering Manager calls the timing).
Still blocked on a real deployment-event source. The natural trigger is Phase
5 (Launch) standing up a real deploy pipeline — at that point 9.7 unblocks
with real data instead of synthesized events, which is the whole reason it's
been deferred through every prior sub-stage decision.

**Phase 4 — Remaining Phase 3, gated on 9.7/9.10:**
- 9.11 Release Risk Analysis (needs 9.4 ✅, 9.7, 9.10)
- 9.12 Release Advisor (needs 9.11)
- 9.13 Incident Analysis (needs 9.9 ✅, 9.11)
- 9.17 Knowledge Graph — kept last per the roadmap's own stated intent
  (synthesizes every other capability's output), even though its literal
  listed dependencies (9.9, 9.16) would technically clear earlier.

**Phase 5 — Launch** (Open Source Maintainer, Staff Platform/DevOps Engineer,
CEO sign-off) — full detail in §4 below: real GitHub App registration,
secrets, staging rollout, first real end-to-end validation against live
GitHub (never exercised — every test uses mocked HTTP or fake reasoning
ports by design). **This phase needs real action from the user** (GitHub App
account, cluster/domain) — it cannot be completed by writing code alone.

**Phase 6 — Stage 10 Optimization** (Staff Backend/Platform Engineer, DB
Architect, CTO review). Load/chaos testing can start against local/staging
environments in parallel with Phases 2–5 — it doesn't need real production
traffic. Only the cost-per-unit-of-value number needs an actual usage window
after Phase 5.

Phases 2 and 6 are not strictly sequential with each other or with Phase 5 —
per "Entry criteria for Stage 10" below, Stage 10 can interleave with
Phase 2/3 sub-stage work once something is actually running. Phase 1 (DoD
gaps) and the license decision are the only genuinely blocking prerequisites
before anything else in this list.

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

- ~~**License**~~ — resolved 2026-07-07: Apache-2.0.
- ~~**`pr_analysis.pr_risk_assessment.llm_tokens_used`/`llm_latency_ms`**~~ —
  resolved 2026-07-07: backfilled in both `pr_analysis` and (the also-gapped)
  `root_cause_analysis`. See the Phase 1 roadmap entry above.
- **`worker.py` has no HTTP server**, but the Helm chart's
  `worker-deployment.yaml` configures `httpGet` liveness/readiness probes
  against it — discovered 2026-07-07 while building the `Dockerfile`. Real
  Kubernetes deployment of the worker would fail its probes today. Not yet
  fixed — candidate for folding into the OpenTelemetry instrumentation pass.

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

- [x] **License decision** — Apache-2.0, decided 2026-07-07.
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
- [x] CI activated and green (§3).
- [x] `Dockerfile`s exist — added 2026-07-07 (multi-stage, `api`/`worker`
      targets, both built and verified locally). `build` job's CI step still
      needs a real GitHub Actions run to confirm it builds there too (not yet
      re-verified since this change) — and the worker's missing health
      endpoint (noted in §1) means it isn't yet safely deployable even once
      the image builds.

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
