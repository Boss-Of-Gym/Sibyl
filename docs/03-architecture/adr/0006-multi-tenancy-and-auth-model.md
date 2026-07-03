# ADR-0006: Single-tenant deployment shape, multi-tenant-ready schema

**Status:** Accepted (2026-07-02)

## Context

Sibyl could be built as a SaaS-shaped multi-tenant system or a single-tenant
self-hosted OSS tool. This affects the Identity/Access context and the shape of
every other context's data model (whether every row needs a tenant-scoping key).

## Decision

**Single-tenant per deployment for MVP**: one Sibyl installation is installed (as a
GitHub App) against one organization's repositories; there is no cross-organization
data model or billing/plan concept in MVP.

**However**, every persisted entity carries an `installation_id` (and, transitively,
`organization_id`) scoping key from day one, even though MVP never queries across
more than one installation. Retrofitting a tenant key onto an existing schema and
every query later is expensive and error-prone (easy to miss a query and leak data
across tenants); adding the column now, unused beyond a single value, costs
nothing.

## Alternatives considered

- **Fully multi-tenant from day one** (tenant-aware auth, plan/billing concepts,
  per-tenant rate limiting). Rejected: no evidence (Stage 1) or product requirement
  (Stage 2) calls for multi-tenant SaaS yet; building it now is speculative scope
  the project's own "no half-finished implementations" rule warns against.
- **No tenant key at all, add it later if needed.** Rejected: this is the
  expensive-to-retrofit path — every table and query would need revisiting, and a
  missed spot becomes a real cross-tenant data leak, not just a bug.

## Consequences

- Positive: MVP stays simple (no tenant-switching logic, no plan/billing model) while
  not foreclosing a future multi-tenant SaaS version.
- Negative: the `installation_id` column is unused complexity until multi-tenancy is
  actually needed — accepted, because the cost of carrying an unused column is far
  lower than the cost of retrofitting one.
- Follow-up: Stage 5 (API Design) auth scopes are defined per-installation from the
  start, consistent with this decision.
