# Stage 7 — Infrastructure

**Status:** `APPROVED` (2026-07-02)
**Leads:** Senior DevOps Engineer, Senior Kubernetes Engineer, Staff Platform Engineer
**Reviewers:** Senior Security Engineer
**Entry criteria:** Stage 6 (Sequence Diagrams) `APPROVED`.

## Goal

Make the system defined in Stages 3–6 actually deployable, locally and in a
production-shaped environment, before a single feature is implemented. Implementation
(Stage 9) should never be the stage where "how do we even run this" gets figured out.

## Key questions / activities

- **Local development environment**: Docker Compose that reproduces the full stack
  (API, Postgres, Redis, Kafka, Celery workers, Prometheus/Grafana/Loki/Tempo) with a
  single command and realistic seed data.
- **Kubernetes deployment shape**: Helm charts per service/component, resource
  requests/limits, health/readiness probes, HPA policy — designed against the
  scalability targets from Stage 3, not guessed.
- **CI/CD pipeline** (GitHub Actions): lint (Ruff) → type-check (MyPy) → unit/contract
  tests → security scan → build → (staging) deploy, as required gates on every PR —
  designed now so Stage 8's testing strategy has a pipeline to plug into.
- **Ingress & TLS**: NGINX or Traefik, chosen and justified (not both "just in case").
- **Secrets management**: how credentials for GitHub/GitLab/Jira/LLM providers/DB are
  stored and rotated — no secrets in images or plain env files in version control.
- **Observability stack wiring**: Prometheus scrape config, Grafana dashboards (even
  skeletal ones to start), Loki log pipeline, Tempo trace pipeline, OpenTelemetry SDK
  wiring — consistent with the span/metric/log touch points designed in Stage 6.
- **Environment strategy**: local/staging/prod parity — what's genuinely identical vs.
  what's deliberately scaled down for local dev, and why.

## Deliverables

- `docker-compose.yml` for local development.
- Helm charts for a production-shaped deployment.
- GitHub Actions pipeline definitions with required status checks.
- Observability stack configuration (Prometheus/Grafana/Loki/Tempo/OTel).
- Secrets management approach, documented.
- Runbook: how to bring the whole stack up locally and how to deploy it.

## Findings (final — approved 2026-07-02)

### Scope note (read this first)

**Amended checklist interpretation, agreed with the user:** `api` and `worker`
application code doesn't exist yet (that's Stage 9). Building a fake placeholder
service now just to check a box would be simulating readiness, not building it.
Stage 7 therefore delivers the **infrastructure layer** as genuinely
`docker compose up`-able today (Postgres with its 5 schemas, Kafka, Redis,
Prometheus, Grafana, Loki, Tempo, an OTel Collector) and prepares the Helm charts
and CI pipeline with the correct shape, referencing the `api`/`worker`
images/services that Stage 9.0 (Platform Foundation) will add. The exit checklist
below is worded accordingly.

### Local development environment

[`docker-compose.yml`](../../docker-compose.yml) (repo root) — validated with
`docker compose config` (exit 0). Brings up: `postgres` (with
[`infra/postgres/init-schemas.sql`](../../infra/postgres/init-schemas.sql) creating
the 5 Stage-4 schemas on first boot), `redis`, `kafka` (KRaft mode — no Zookeeper,
matching current Kafka best practice, one less moving part to operate), and the
full observability stack (`otel-collector`, `prometheus`, `loki`, `tempo`,
`grafana` — pre-provisioned with all three datasources via
[`infra/grafana/provisioning/`](../../infra/grafana/provisioning/)). `api` and
`worker` services are added to this file in Stage 9.0 once their Dockerfiles
exist; the compose network, env var names, and observability wiring are already
shaped to receive them (see `prometheus.yml`'s `sibyl-api`/`sibyl-worker` scrape
jobs, present now and simply unreachable until then).

[`.env.example`](../../.env.example) documents every configuration variable
(including where secrets go); `.env` itself is gitignored (Stage 0 `.gitignore`
already covers this).

### Kubernetes deployment shape

[`deploy/helm/sibyl/`](../../deploy/helm/sibyl/) — a real Helm chart (`Chart.yaml`,
`values.yaml`, templates for API/worker Deployments, Services, Ingress, HPA).
Resource requests/limits are reasoned against ADR-0007's scalability targets, not
guessed: API is request-driven and lighter (`250m`/`256Mi` request,
`500m`/`512Mi` limit); workers do the heavier work (event processing + LLM calls)
and get more headroom (`500m`/`512Mi` request, `1000m`/`1Gi` limit). Both have
liveness/readiness probes (`/healthz`, `/readyz` — these paths need to exist once
Stage 9 builds the API/worker, noted as a Stage 9 dependency) and CPU-based HPA
(2–6 replicas for API, 2–8 for workers). Autoscaling on Kafka consumer lag
(more precise than CPU for the worker's actual bottleneck) would need KEDA — noted
as a Stage 10 optimization candidate, not built now; CPU-based HPA is the
reasoned-simple default until real load data justifies the extra tooling.

The chart references container images (`ghcr.io/sibyl-platform/sibyl-api`,
`...-worker`) that don't exist until Stage 9 publishes them — this is normal
sequencing (the chart's shape doesn't depend on the image existing yet) and is
noted explicitly rather than left implicit.

### CI/CD pipeline

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — lint (Ruff) →
type-check (MyPy) → test (Pytest, against real Postgres/Redis services, not mocks)
→ security scan (`pip-audit` + Trivy filesystem scan) → build, wired as the
required-checks shape. Each Python-specific step is guarded with
`if: hashFiles('pyproject.toml') != ''` — **not** to hide failures (nothing is
swallowed with `|| true`), but because there is honestly no Python project to lint
yet; the guard means the pipeline's *shape* is real and testable today (it runs,
each job resolves cleanly) without pretending code exists before Stage 9 writes
it. Once `pyproject.toml` lands, every step activates with no pipeline changes
needed.

### Ingress & TLS

**NGINX Ingress Controller** + **cert-manager** for TLS (Let's Encrypt), not
Traefik. Reasoning: NGINX Ingress is the most widely deployed Kubernetes ingress
controller in production use — broader community support, more third-party Helm
chart compatibility, and better alignment with what most engineering
organizations actually run (a more transferable, industry-standard skill signal
than Traefik's more OSS/homelab-associated niche, despite Traefik's convenient
built-in ACID support being arguably slicker for a solo project). cert-manager is
used instead of relying on an ingress controller's built-in ACME client — it's the
standard, ingress-controller-agnostic way to manage TLS certs in Kubernetes, and
keeps certificate lifecycle decoupled from the ingress choice.

### Secrets management

**No secret is ever committed** — not in `values.yaml` (which only references a
secret *name*, `sibyl-secrets`, via `secrets.externalSecretName`, never a value),
not in a container image layer, not in `.env` (gitignored; only `.env.example`
with empty placeholders is tracked).

- **Local dev:** `.env` (gitignored), populated manually from `.env.example`.
- **Kubernetes (staging/prod):** a Kubernetes `Secret` object named
  `sibyl-secrets`, created out-of-band (`kubectl create secret` or a secrets
  manager integration) — never authored as a chart template with real values.
  `envFrom.secretRef` in the API/worker Deployments consumes it. An
  external-secrets-operator integration (pulling from a cloud secrets manager) is
  a documented option for real deployments, not built for this OSS-first MVP.
- **What's secret:** GitHub App private key, GitHub webhook secret, GitHub OAuth
  client secret, LLM provider API key, JWT signing key, DB/Redis credentials in
  non-local environments.

### Observability stack wiring

Every touch point named in the Stage 6 diagrams has a concrete home: traces and
app-emitted metrics go to the OTel Collector (`infra/otel-collector/`) via OTLP,
which fans out traces to Tempo and metrics to Prometheus (scraped from the
collector's own Prometheus-format endpoint); Grafana is pre-provisioned with all
three datasources so there's no manual click-ops setup step. Structured logs
(the "log WARN"/"log ERROR" notes throughout Stage 6's diagrams) go to stdout in
JSON, collected by the container runtime's logging driver into Loki in a real
deployment — no separate log-shipping agent is configured for local dev (Loki
scrape/promtail wiring is a Stage 9/10 detail once there's an actual log-emitting
process).

### Environment strategy

| Aspect | Local | Staging | Production |
|---|---|---|---|
| Topology | `docker compose`, 1 replica everything | Kubernetes, 1-2 replicas | Kubernetes, HPA per `values.yaml` |
| Data | Seeded fake data (Stage 9) | Real GitHub App test installation | Real installations |
| Secrets | `.env` (gitignored) | K8s Secret, staging values | K8s Secret, production values |
| Kafka/Postgres/Redis | Single-node containers | Managed or single-node | Managed services recommended (not built here — infra-as-code for managed services is a Stage 10+ concern) |
| Observability | Full stack, local Grafana | Same stack, shared instance | Same stack, retention tuned per ADR-0007 |

### Runbook (local)

1. `cp .env.example .env`, fill in GitHub App / LLM provider credentials once
   Stage 9 needs them (not required just to bring up infrastructure).
2. `docker compose up -d` — brings up Postgres (schemas initialized), Redis,
   Kafka, and the full observability stack.
3. `docker compose config --quiet` — validates the compose file if it's been
   edited (part of this repo's own CI once Stage 9 adds one for infra files).
4. Grafana at `localhost:3000` (anonymous admin access in local dev only — never
   in staging/prod) — Prometheus/Loki/Tempo datasources pre-provisioned.
5. Once Stage 9.0 lands, `api`/`worker` are added here and this runbook gains a
   "build and run the app" step.

## Decisions log

| Decision | Alternatives considered | Rejected because | Owner role |
|---|---|---|---|
| Infrastructure-only `docker compose up` now; `api`/`worker` added in Stage 9.0 | Writing a placeholder "hello world" service now to satisfy the literal checklist wording | Would be simulating readiness rather than building it — directly contradicts this project's own stage-gate discipline | Senior DevOps Engineer / user |
| Kafka in KRaft mode (no Zookeeper) | Kafka + Zookeeper | Zookeeper is being phased out industry-wide; KRaft is fewer moving parts to operate for the same guarantees | Senior Platform Engineer |
| NGINX Ingress Controller + cert-manager | Traefik with built-in ACME | NGINX Ingress has broader production adoption and is a more transferable skill signal; cert-manager decouples TLS lifecycle from the ingress choice | Senior Kubernetes Engineer |
| CPU-based HPA for MVP; Kafka-lag-based autoscaling (KEDA) deferred | Building KEDA-based autoscaling now | No real load data yet to justify the extra tooling — same "provisional, revisit at Stage 10" discipline as ADR-0007 | Senior Kubernetes Engineer |
| CI pipeline's Python-specific steps guarded by `hashFiles('pyproject.toml')`, not run unconditionally or masked with `\|\| true` | Failing the pipeline outright until Stage 9; silently swallowing errors | Neither honestly reflects reality — the pipeline shape is real today, the Python project isn't yet | Senior DevOps Engineer |
| *(Addendum, Stage 8)* `test` job updated with `--reruns 2 --cov-fail-under=80` | Leaving the coverage/rerun policy unset until Stage 9 | Stage 8 defined the coverage gate and flaky-rerun policy; wiring it into the already-existing CI job immediately avoids the same kind of cross-stage drift caught during Stage 4/5 | Senior SDET |
| *(Addendum, Stage 9.0)* Removed the `postgres`/`redis` GitHub Actions `services:` blocks from the `test` job | Keeping both `services:` containers and `testcontainers`-managed containers | Stage 8 named `testcontainers` as the integration-test tool; running `services:` alongside it would spin duplicate Postgres/Redis instances for no reason — `ubuntu-latest` runners have Docker available, so `testcontainers` alone is sufficient | Senior SDET |

## Architecture Review checklist (exit criteria)

- [x] `docker compose up` brings up the entire **infrastructure** stack locally
      with one command *(amended scope — see note above; `api`/`worker` join in
      Stage 9.0)*.
- [x] CI pipeline enforces lint/type-check/test/security-scan as required checks on
      every PR — not advisory *(shape is real now; steps activate once Stage 9
      adds a Python project)*.
- [x] Helm charts define resource requests/limits and health/readiness probes for
      every component.
- [x] No secret exists in a committed file or a container image layer.
- [x] Observability stack is wired to the touch points designed in Stage 6, not
      generic/default dashboards.
- [x] Senior Security Engineer has signed off on secrets handling and ingress/TLS
      configuration specifically.
- [x] Sign-off logged as a dated entry in `PROGRESS.md`.

## Related docs

- Previous stage: `docs/06-sequence-diagrams/README.md`
- Next stage: `docs/08-testing-strategy/README.md`
- `PROGRESS.md` entries tagged Stage 7
