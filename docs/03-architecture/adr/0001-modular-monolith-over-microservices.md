# ADR-0001: Modular monolith over microservices for v1

**Status:** Accepted (2026-07-02)

## Context

Sibyl's MVP (Stage 2) covers 4 capabilities (PR Analysis, Test Impact Analysis,
Flaky Detection, Root Cause Analysis) built by a single developer, with no
production traffic yet. Microservices are the "expected" architecture for a
platform demonstrating distributed-systems maturity, but they carry real,
non-optional operational cost: service discovery, network calls where function
calls would do, per-service CI/CD pipelines and Helm charts, distributed tracing
needed just to debug correctness (not only performance), and data-consistency
patterns (sagas, eventual consistency across service boundaries) that only pay off
once a boundary is actually under independent scaling or ownership pressure.

## Decision

Build a **modular monolith**: one codebase, one shared domain model, with bounded
contexts (ADR-0002) enforced by hexagonal ports/adapters and package boundaries —
not a single running process. The system is deployed as multiple Kubernetes
workloads sharing this codebase (an API deployment serving FastAPI, one or more
worker deployments consuming Kafka topics), so it already exercises real
distributed-systems concerns (async processing, idempotent consumers, eventual
consistency between write-side processing and read-side projections) without
service-to-service network calls between business domains that have no proven need
to be independently deployed yet.

## Alternatives considered

- **Microservices per capability** (PR Analysis, Test Intelligence, Root Cause
  Analysis, Ingestion each as a separately deployed service). Rejected: none of
  these contexts has an independent scaling profile or ownership boundary yet — the
  entire system is built and operated by one person. The operational tax (network
  boundaries, distributed tracing, per-service deployment pipelines) would be paid
  immediately while the benefit (independent scaling/deployment) has no current
  use. This is the textbook premature-distribution mistake ("resume-driven
  microservices").
- **Single undifferentiated monolith** (no enforced internal boundaries). Rejected:
  would make a later extraction into services (if a real scaling need emerges)
  require a rewrite rather than a "cut along the seam" — and would blur the DDD
  bounded-context discipline this project is meant to demonstrate.

## Consequences

- Positive: much lower operational cost for a single-developer project; bounded
  contexts still demonstrate DDD discipline; Kafka-based event backbone still
  demonstrates real async/distributed-systems patterns; extraction to services later
  is a scoped, seam-based operation, not a rewrite, *provided* context boundaries
  are actually respected in code (no cross-context imports of internal models).
- Negative: doesn't demonstrate service-mesh/multi-service K8s orchestration
  directly — mitigated by still running multiple deployables (API + workers) in
  Kubernetes, and by the option to extract a context into its own service later if
  a concrete reason emerges (e.g., Stage 10 load testing reveals one context needs
  independent scaling).
- Follow-up: bounded context boundaries (ADR-0002) must be enforced by tooling
  (package structure, import-linter or similar) once Stage 9 implementation starts,
  or this decision quietly erodes.
