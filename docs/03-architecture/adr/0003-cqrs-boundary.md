# ADR-0003: CQRS applied selectively, not platform-wide

**Status:** Accepted (2026-07-02)

## Context

CQRS (separating write-side domain handling from read-side query models) is one of
the architectural qualities this project sets out to demonstrate (per
`MASTER_PROMPT.md` pinned scope). Applying it uniformly everywhere, regardless of
whether a given context needs it, would be exactly the kind of undemonstrated,
box-ticking usage a senior reviewer would (rightly) call out.

## Decision

Apply CQRS to **PR Analysis, Test Intelligence, and Root Cause Analysis** only.
Each of these: (a) receives writes asynchronously and continuously from Kafka
events, and (b) is queried frequently and synchronously (API calls, GitHub Checks
rendering) with different shape needs than the write-side processing produces
directly — a denormalized read model (e.g., "latest analysis result for PR #123,
ready to render") pays for its complexity here.

**Do not** apply CQRS to **Ingestion** or **Identity/Access** — Ingestion is
essentially write-only (normalize and publish, no complex queries against it
directly), and Identity/Access is a simple, low-volume, mostly-CRUD context where a
separate read model would be unjustified complexity.

## Alternatives considered

- **CQRS everywhere, for consistency.** Rejected: consistency is not a reason on
  its own; it would add complexity to Ingestion and Identity/Access with no query
  pattern that needs it, contradicting the project's own "justify, don't assume"
  rule for CQRS (Stage 3 key questions).
- **No CQRS anywhere, single model for read and write.** Rejected: would force the
  3 analytical contexts to serve API/GitHub-Checks reads directly off the
  write-side domain model shaped for event processing, which doesn't match the
  read access pattern (single-entity lookup by PR/commit) and would couple the read
  API's shape to internal write-side representations.

## Consequences

- Positive: CQRS is applied where it has a concrete justification, which is also
  the more defensible story in review ("here's why," not "everywhere, because
  CQRS").
- Negative: two different internal patterns exist in the same codebase (CQRS
  contexts vs. simple-CRUD contexts) — acceptable, and worth calling out explicitly
  in code/docs so it reads as a decision, not an inconsistency.
