import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from eval.models import PrAnalysisGoldenCase, RootCauseGoldenCase
from eval.scoring import ScoreResult, score_pr_risk_assessment, score_root_cause_explanation
from sibyl.platform.config import Settings, get_settings
from sibyl.pr_analysis.adapters.llm_reasoning import AnthropicReasoningPort as PrAnalysisPort
from sibyl.root_cause_analysis.adapters.llm_reasoning import (
    AnthropicReasoningPort as RootCausePort,
)

GOLDEN_SETS_DIR = Path(__file__).parent / "golden_sets"
PASS_RATE_GATE = 0.8

Capability = Literal["pr-analysis", "root-cause-analysis"]


def _load_cases[CaseT: BaseModel](path: Path, model: type[CaseT]) -> list[CaseT]:
    cases = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            cases.append(model.model_validate(json.loads(line)))
    return cases


def _report(case_id: str, result: ScoreResult) -> None:
    print(f"[{'PASS' if result.passed else 'FAIL'}] {case_id}")
    for reason in result.reasons:
        print(f"    - {reason}")


async def _run_pr_analysis(settings: Settings) -> tuple[int, int]:
    port = PrAnalysisPort(settings.llm_provider_api_key, settings.llm_provider_model)
    cases = _load_cases(GOLDEN_SETS_DIR / "pr_analysis.jsonl", PrAnalysisGoldenCase)
    passed = 0
    for case in cases:
        assessment = await port.assess_pr_risk(case.context)
        result = score_pr_risk_assessment(case.expected, assessment)
        _report(case.id, result)
        passed += int(result.passed)
    return passed, len(cases)


async def _run_root_cause_analysis(settings: Settings) -> tuple[int, int]:
    port = RootCausePort(settings.llm_provider_api_key, settings.llm_provider_model)
    cases = _load_cases(GOLDEN_SETS_DIR / "root_cause_analysis.jsonl", RootCauseGoldenCase)
    passed = 0
    for case in cases:
        explanation = await port.explain_root_cause(case.context)
        result = score_root_cause_explanation(case.expected, explanation)
        _report(case.id, result)
        passed += int(result.passed)
    return passed, len(cases)


async def _run(capability: Capability) -> int:
    settings = get_settings()
    if not settings.llm_provider_api_key:
        print("LLM_PROVIDER_API_KEY is not set — cannot eval against the real provider.")
        return 1

    if capability == "pr-analysis":
        passed, total = await _run_pr_analysis(settings)
    else:
        passed, total = await _run_root_cause_analysis(settings)

    pass_rate = passed / total if total else 0.0
    print(f"\n{passed}/{total} passed ({pass_rate:.0%}), gate is {PASS_RATE_GATE:.0%}")
    return 0 if pass_rate >= PASS_RATE_GATE else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a golden-set eval against the real LLM provider."
    )
    parser.add_argument("capability", choices=["pr-analysis", "root-cause-analysis"])
    args = parser.parse_args()
    return asyncio.run(_run(args.capability))


if __name__ == "__main__":
    sys.exit(main())
