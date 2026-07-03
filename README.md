# Sibyl

**Ask before you ship.**

> **Status: Stage 9 in progress — all 4 confirmed-MVP capabilities shipped,
> plus four Phase 2 capabilities.** Platform Foundation, PR Analysis,
> Test Impact Analysis, Flaky Detection, Root Cause Analysis, CI/CD
> Optimization, Coverage Intelligence, Dependency Analysis, and API Evolution
> Tracking are implemented and tested — 217 tests, 93% coverage, against real
> Postgres/Redis/Kafka plus contract-tested GitHub API calls.
> `docker compose up` brings up
> Postgres/Kafka/Redis and the full observability stack today — see
> [Project status & process](#project-status--process). This project is built
> using an explicit, stage-gated engineering process; each capability under
> `src/sibyl/` only exists once its own Stage 9 sub-stage is `APPROVED` — see
> [`docs/00-process/README.md`](docs/00-process/README.md) for why.

Sibyl is an open-source **Engineering Intelligence Platform** that analyzes the full
software development lifecycle —
pull requests, tests, CI/CD, deployments, incidents, and architecture drift — by
correlating signal that today sits siloed across GitHub, GitLab, Jira, Confluence,
CI/CD, Kubernetes, and the observability stack, and using an LLM to turn that
correlated signal into decisions engineers and engineering managers can act on.

## Why this exists

Most of the signal needed to answer "is this release safe to ship," "why did this
test start failing," or "which service is quietly accumulating risk" already exists —
scattered across a dozen tools, in a shape only a human correlating tabs can currently
use. This platform's bet is that an LLM's value here isn't chat, it's **synthesis
across noisy, semi-structured, cross-system signal** — turning scattered facts into a
specific, defensible recommendation. The full problem statement, target users, and
evidence for this bet are being developed in
[`docs/01-problem-discovery/`](docs/01-problem-discovery/README.md) — deliberately
*before* any feature below is treated as settled scope.

## Candidate capabilities

Of these 17 candidates, **PR Analysis, Test Impact Analysis, Flaky Detection, and
Root Cause Analysis are the confirmed MVP** — the only four directly evidenced by
real problems identified during Problem Discovery (see
[`docs/01-problem-discovery/`](docs/01-problem-discovery/README.md)). The rest are
sequenced into later phases — see
[`docs/02-product-discovery/`](docs/02-product-discovery/README.md) for the full
scoring and phasing rationale, and the dependency-ordered build sequence in
[`docs/09-implementation/README.md`](docs/09-implementation/README.md).

| Category | Capabilities |
|---|---|
| Change & risk analysis | PR Analysis, Root Cause Analysis, Regression Prediction, Release Risk Analysis, Release Advisor |
| Test intelligence | Test Impact Analysis, Flaky Detection, Coverage Intelligence, Test Generation |
| Operational intelligence | Incident Analysis, CI/CD Optimization, Engineering Metrics |
| Structural intelligence | API Evolution Tracking, Dependency Analysis, Architecture Insights, Knowledge Graph |
| AI-generated artifacts | AI Documentation, Test Generation |

## Architecture principles (target)

The system is designed to demonstrate, and actually use, rather than merely gesture
at: Domain-Driven Design (5 bounded contexts), Hexagonal/Clean Architecture
(everything behind ports/adapters, including the LLM), CQRS where it earns its
complexity (3 of 5 contexts, not all), Event-Driven Architecture for the
ingestion-to-analysis pipeline, and SOLID throughout. A **modular monolith**, not
microservices, was chosen deliberately for v1 — every non-trivial architectural
decision, including that one, is recorded as an ADR under
`docs/03-architecture/adr/` with rejected alternatives and cost reasoning, not just
asserted.

## Tech stack

| Layer | Choice |
|---|---|
| Language / runtime | Python 3.13 |
| API | FastAPI |
| Data | PostgreSQL, SQLAlchemy 2, Alembic, Pydantic v2 |
| Cache / broker | Redis |
| Streaming | Kafka |
| Background work | Celery |
| Containers / orchestration | Docker, Docker Compose, Kubernetes, Helm |
| Ingress | NGINX / Traefik |
| CI/CD | GitHub Actions |
| Observability | Prometheus, Grafana, Loki, Tempo, OpenTelemetry |
| AuthN/AuthZ | OAuth2, JWT |
| Testing | Pytest, Playwright |
| Tooling | uv, Ruff, MyPy, pre-commit |

This stack is treated as fixed scope for the project; any change to it is itself
logged as an explicit decision internally, not a silent drift.

## Project status & process

This repository is built stage-by-stage, in order, with an explicit review gate
between stages — code is deliberately one of the *last* things written, not the
first. The full rationale and mechanics live in
[`docs/00-process/README.md`](docs/00-process/README.md); the table below is kept in
sync with the project's internal engineering log.

| # | Stage | Status |
|---|---|---|
| 0 | Process Bootstrap | ✅ Done |
| 1 | Problem Discovery | ✅ Done |
| 2 | Product Discovery | ✅ Done |
| 3 | Architecture | ✅ Done |
| 4 | Database | ✅ Done |
| 5 | API Design | ✅ Done |
| 6 | Sequence Diagrams | ✅ Done |
| 7 | Infrastructure | ✅ Done |
| 8 | Testing Strategy | ✅ Done |
| 9 | Implementation (17 capabilities, dependency-ordered) | 🔶 In progress — 9.0, 9.1, 9.2, 9.3, 9.9 done (all confirmed-MVP capabilities) plus 9.5, 9.4, 9.6, 9.8 (four of five Phase 2) |
| 10 | Optimization | ⬜ Not started |

*(This table is updated manually as each stage progresses.)*

For the cross-cutting plan tying together remaining development sequencing,
debugging practice, CI/CD activation, and the path to a real launch, see
[`docs/OPERATIONS_STRATEGY.md`](docs/OPERATIONS_STRATEGY.md) — a living
document, not itself stage-gated.

## Repository map

```
pyproject.toml       — Python 3.13 project: FastAPI, SQLAlchemy 2, Alembic, Ruff, MyPy (strict), pytest
src/sibyl/           — application code: identity/, ingestion/, platform/ (shared kernel), api/,
                       pr_analysis/, test_intelligence/, root_cause_analysis/,
                       dependency_analysis/ (bounded contexts)
alembic/             — schema migrations, one independent branch per bounded-context schema
tests/               — unit / contract (mocked HTTP) / integration (real Postgres/Redis/Kafka via testcontainers)
docker-compose.yml   — local dev stack: Postgres, Kafka, Redis, full observability
.env.example         — configuration template (no secrets)
infra/               — Postgres init, Prometheus/Loki/Tempo/OTel Collector/Grafana config
deploy/helm/sibyl/   — Kubernetes Helm chart
.github/workflows/   — CI pipeline (lint, type-check, test, security scan, build)
docs/
  00-process/      — the engineering process definition + reusable templates
  01-problem-discovery/ ... 10-optimization/ — one folder per lifecycle stage
```

## Name & repository description

Sibyl (Sibylla/Pythia — the oracle of Delphi) reflects what the platform actually
does: it doesn't just display metrics, it correlates noisy signal across your
toolchain into a specific, defensible answer to "is this safe to ship." The name
follows the same one-word, evocative naming convention as the observability stack
this project integrates with (Prometheus, Grafana, Loki, Tempo) rather than a
marketing-style compound like "ShipIQ" or "ReleaseInsight."

**GitHub repository description** — copy into *Settings → About → Description* once
this is pushed (fits GitHub's 350-character limit with room to spare):

> Open-source, LLM-powered engineering intelligence platform. Correlates signal
> across GitHub, GitLab, Jira, CI/CD, Kubernetes, and your observability stack to
> answer one question before you ship: is this safe?

**GitHub topics** — copy into *Settings → About → Topics* for discoverability:

`engineering-intelligence` `developer-productivity` `devops` `platform-engineering`
`sdlc` `llm` `ai` `observability` `ci-cd` `dora-metrics` `python` `fastapi`
`kubernetes`

**Social preview / meta description** (shorter form, for link previews and search
snippets — under ~160 characters):

> Sibyl correlates signal across your dev toolchain and uses an LLM to tell you,
> with evidence, whether it's safe to ship.

## Contributing

Platform Foundation (auth, event backbone, GitHub webhook ingestion) is
implemented and tested. This project isn't accepting external feature work yet —
the remaining MVP capabilities (Test Impact Analysis, Flaky Detection, Root Cause
Analysis) aren't built, and contribution guidelines need that shape to be
meaningful. Until then, the most useful contribution is scrutiny of the reasoning
in `docs/01-problem-discovery/` through `docs/09-implementation/`.

## License

Not yet decided — to be finalized during Product Discovery.
