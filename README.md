# Sibyl

**Ask before you ship.**

> **Status: pre-design (Stage 0 of 10 complete).** This project is being built using
> an explicit, stage-gated engineering process — see [Project status & process](#project-status--process)
> before judging it by the (currently empty) `src/` tree. No implementation exists yet
> by design: see [`docs/00-process/README.md`](docs/00-process/README.md) for why.

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

These 17 capabilities are the candidate scope explored during Problem/Product
Discovery. Which ones make the MVP, and in what order the rest ship, is a Stage 2
decision — see [`docs/02-product-discovery/`](docs/02-product-discovery/README.md) and
the dependency-ordered build sequence in
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
at: Domain-Driven Design, Hexagonal/Clean Architecture, CQRS where it earns its
complexity, Event-Driven Architecture for ingestion and analysis pipelines, and SOLID
throughout. Every non-trivial architectural decision is recorded as an ADR under
`docs/03-architecture/adr/` once Stage 3 begins — decisions are argued and justified,
not asserted.

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
| 1 | Problem Discovery | ⬜ Not started |
| 2 | Product Discovery | ⬜ Not started |
| 3 | Architecture | ⬜ Not started |
| 4 | Database | ⬜ Not started |
| 5 | API Design | ⬜ Not started |
| 6 | Sequence Diagrams | ⬜ Not started |
| 7 | Infrastructure | ⬜ Not started |
| 8 | Testing Strategy | ⬜ Not started |
| 9 | Implementation (17 capabilities, dependency-ordered) | ⬜ Not started |
| 10 | Optimization | ⬜ Not started |

*(This table is updated manually as each stage progresses.)*

## Repository map

```
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

This project isn't accepting external feature work yet — it has no implementation.
Once Stage 7 (Infrastructure) is complete and the repo is runnable, contribution
guidelines will be added under `docs/00-process/` and linked here. Until then, the
most useful contribution is scrutiny of the reasoning in `docs/01-problem-discovery/`
through `docs/08-testing-strategy/` as each is filled in.

## License

Not yet decided — to be finalized during Product Discovery.
