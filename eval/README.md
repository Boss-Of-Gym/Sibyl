# LLM Golden-Set Eval

Implements the LLM evaluation framework frozen in
[`docs/08-testing-strategy/README.md`](../docs/08-testing-strategy/README.md#llm-evaluation-framework):
unit/contract tests never call a real LLM (`FakeReasoningPort`), and the real
adapter (`AnthropicReasoningPort`) is validated separately against a curated
golden set, scored on structured fields rather than free-text exact-match.

## Honesty note

The golden-set cases in `golden_sets/*.jsonl` are **synthetic, not drawn from
real production PRs or failures** — this project has no real usage history
yet (no GitHub App installation, no deployed instance). They're written to be
structurally realistic (plausible file paths, diff sizes, risk gradients),
not fabricated to make numbers look good. Replace them with real examples as
soon as real usage exists, per the Stage 8 decision.

This harness has **never been run against a live Anthropic API call** — this
environment has no `LLM_PROVIDER_API_KEY` configured. The scoring logic
(`scoring.py`) is unit-tested (`tests/unit/eval/test_scoring.py`) against
constructed `RiskAssessment`/`RootCauseExplanation` objects, so it's known to
score correctly — what's unverified is the harness's real API call path
(`run_golden_set.py`'s `_run_pr_analysis`/`_run_root_cause_analysis`). Verify
this end-to-end the first time a real key is available, before trusting the
CI gate.

The cost/latency budget tests the Stage 8 doc also calls for ("using the fake
port's recorded historical costs from the real adapter's telemetry") are
**not implemented** — there is no real historical telemetry to source them
from yet (nothing has been deployed). Revisit once real usage data exists,
the same evidence-before-speculation principle Stage 10 applies elsewhere.

## Format

Each line in `golden_sets/{capability}.jsonl` is one case:

```json
{
  "id": "unique-slug",
  "notes": "why this case exists / what it's testing for",
  "context": { /* PrRiskContext or RootCauseContext, exact domain schema */ },
  "expected": { /* structured-field expectation, see models.py */ }
}
```

Expectations are **bands and matches, not exact values** — `score_min`/
`score_max` for PR Analysis, `confidence_min` (+ optional
`suspected_file_path`) for Root Cause Analysis — because LLM output is
non-deterministic even with structured tool-calling.

## Running

Requires `LLM_PROVIDER_API_KEY`/`LLM_PROVIDER_MODEL` set (real Anthropic
credentials — this calls the live API, it costs money and takes real time):

```bash
uv run python -m eval.run_golden_set pr-analysis
uv run python -m eval.run_golden_set root-cause-analysis
```

Exits non-zero if the pass rate falls below `PASS_RATE_GATE` (80%) in
`run_golden_set.py`, or immediately if no API key is configured.

## CI

`.github/workflows/llm-eval.yml` runs this on a weekly schedule, on manual
`workflow_dispatch`, and on any PR touching either `llm_reasoning.py`
adapter — per Stage 8's "gate for any prompt or model-version change,"
not "gate for every commit." Each step is guarded on
`secrets.LLM_PROVIDER_API_KEY` being set, so the workflow doesn't show as
perpetually failing before that secret is actually configured in the repo.
