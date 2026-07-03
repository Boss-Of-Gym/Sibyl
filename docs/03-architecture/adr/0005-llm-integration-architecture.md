# ADR-0005: LLM behind a reasoning port, structured tool-calling over RAG

**Status:** Accepted (2026-07-02)

## Context

Stage 1 established that the LLM's job is *synthesis over already-correlated
signal* (diff + test history + past incidents), not retrieval over an unstructured
corpus. The architecture must reflect that distinction, keep the LLM model-agnostic
and swappable, and make LLM output reliable enough to validate and test (Stage 8).

## Decision

Define a **reasoning port** — an interface such as
`ReasoningPort.assess_pr_risk(context) -> RiskAssessment` and
`ReasoningPort.explain_root_cause(context) -> RootCauseExplanation` — implemented by
an adapter that calls a specific LLM provider. No business logic anywhere else
calls a provider SDK directly.

The interaction pattern is **structured tool-calling / constrained generation**:
the calling context (PR Analysis, Root Cause Analysis) assembles the relevant,
already-correlated context itself (via its own domain logic and read models, not
via the LLM), and the LLM's output is required to conform to a Pydantic schema
(e.g. `RiskAssessment(score: float, rationale: str, contributing_factors:
list[Factor])`), validated before it's trusted or persisted. This is not classic
RAG (no retrieval-over-unstructured-corpus step) because the correlation step is
already the domain logic's job, done before the LLM is ever called.

**Guardrails for MVP** (cost/latency, per the Stage 2 guardrail metrics):
- Hard timeout on every LLM call; on timeout or provider error, the context still
  persists and surfaces its non-LLM signal (e.g., "flaky: yes, root cause
  unavailable") rather than blocking or failing the whole analysis.
- Token usage logged per call, tagged by capability, feeding the Stage 2 "LLM cost
  per analysis" guardrail metric directly.
- Single model tier for MVP — no cost-based model routing (cheap-model-first,
  escalate-if-uncertain) yet; that optimization is explicitly deferred to Stage 10,
  once real usage data exists to tune it against instead of guessing.

## Alternatives considered

- **RAG over a vector store of historical PRs/incidents.** Rejected for MVP: the
  problems Stage 1 evidenced are about correlating *this* PR's own diff/test/CI
  signal, not searching semantically similar unstructured text. A retrieval layer
  would add real infrastructure (embeddings, vector store, chunking strategy) to
  solve a retrieval problem the MVP doesn't actually have yet. Revisit once
  cross-PR pattern-matching (e.g., "this looks like the incident from last month")
  becomes an actual Phase 2/3 capability (Incident Analysis, Knowledge Graph).
- **Direct provider SDK calls from domain services.** Rejected: couples business
  logic to a specific vendor, makes swapping models/providers a cross-cutting
  change, and makes Stage 8's deterministic eval strategy harder (can't substitute
  a fixture/mock reasoning implementation for tests).
- **Unstructured free-text LLM output, parsed loosely.** Rejected: not testable or
  reliable enough for something feeding an automated GitHub Check; schema
  validation is required so a malformed LLM response fails loudly instead of
  silently corrupting a read model.

## Consequences

- Positive: LLM provider is swappable behind the port; output is type-safe and
  testable; cost is measurable per the Stage 2 guardrail from day one.
- Negative: constrains the LLM to answering the specific schema asked — less
  flexible than open-ended chat, which is the intended trade-off (Stage 1: this is
  a decision-support tool, not a chatbot).
- Follow-up: Stage 8 must define how `ReasoningPort` is faked/mocked for
  deterministic tests, and how the *real* adapter is evaluated against a golden set
  (LLM-eval strategy) without every CI run making live LLM calls.
