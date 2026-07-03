# ADR-0004: Event-driven backbone for ingestion-to-analysis; synchronous API for reads

**Status:** Accepted (2026-07-02)

## Context

The system needs to decide, concretely, what flows through Kafka versus what's a
direct synchronous call — "it depends" is not an answer Stage 3 accepts.

## Decision

**Synchronous (FastAPI request/response):** any read of an already-computed result
— e.g. fetching the current analysis for a PR. No write path is synchronous beyond
accepting a webhook and immediately acknowledging it (the actual processing happens
async).

**Asynchronous (Kafka):** everything from "webhook received" to "analysis
available." This also matches the GitHub Checks API's own model (a check run is
created as `in_progress` and updated to `completed` later) — the product's
interaction model (Stage 2) is already asynchronous by nature, so the backbone
matches the domain instead of fighting it.

**Draft topic catalog for MVP** (finalized with schemas in Stage 4):

| Topic | Producer | Consumers | Key |
|---|---|---|---|
| `ingestion.pr-changed` | Ingestion (GitHub adapter) | Test Intelligence, PR Analysis | repo + PR number |
| `ingestion.ci-run-completed` | Ingestion (GitHub adapter) | Test Intelligence | repo + commit SHA |
| `test-intelligence.impact-computed` | Test Intelligence | Root Cause Analysis | repo + PR number |
| `test-intelligence.flaky-signal-updated` | Test Intelligence | PR Analysis (optional enrichment) | repo + test ID |
| `pr-analysis.completed` | PR Analysis | Root Cause Analysis, GitHub Checks adapter | repo + PR number |
| `root-cause.hypothesis-ready` | Root Cause Analysis | GitHub Checks adapter | repo + PR number |

## Alternatives considered

- **Fully synchronous pipeline** (webhook triggers a direct call chain that blocks
  until analysis completes). Rejected: LLM calls and multi-context correlation take
  long enough that blocking a webhook handler on them risks GitHub-side timeouts and
  couples Ingestion's availability to every downstream context's latency.
- **Kafka for everything, including reads** (CQRS read side also event-sourced from
  scratch on every query). Rejected: unnecessary complexity for point-lookups; the
  read model (ADR-0003) is a normal queryable projection, not something that needs
  re-derivation per request.

## Consequences

- Positive: ingestion stays fast and decoupled from analysis latency/failures;
  matches GitHub's own async Checks model; natural fit for retries and backpressure
  handling.
- Negative: end-to-end latency (webhook → visible PR comment) is harder to reason
  about than a synchronous chain — must be watched against the Stage 2 guardrail
  metric (PR-opened-to-analysis-available latency).
- Follow-up: exact event schemas, retention, and partitioning are Stage 4 work; this
  ADR fixes the topic boundaries and sync/async split, not the wire format.
