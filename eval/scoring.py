from dataclasses import dataclass, field

from eval.models import PrAnalysisExpectation, RootCauseExpectation
from sibyl.pr_analysis.domain.models import RiskAssessment
from sibyl.root_cause_analysis.domain.models import RootCauseExplanation


@dataclass
class ScoreResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def score_pr_risk_assessment(
    expected: PrAnalysisExpectation, actual: RiskAssessment
) -> ScoreResult:
    if actual.explanation_unavailable:
        return ScoreResult(
            passed=False, reasons=["explanation_unavailable=True — LLM call fell back"]
        )

    reasons = []
    if not (expected.score_min <= actual.score <= expected.score_max):
        reasons.append(
            f"score {actual.score:.2f} outside expected band "
            f"[{expected.score_min}, {expected.score_max}]"
        )
    return ScoreResult(passed=not reasons, reasons=reasons)


def score_root_cause_explanation(
    expected: RootCauseExpectation, actual: RootCauseExplanation
) -> ScoreResult:
    if actual.explanation_unavailable:
        return ScoreResult(
            passed=False, reasons=["explanation_unavailable=True — LLM call fell back"]
        )

    reasons = []
    if actual.confidence < expected.confidence_min:
        reasons.append(
            f"confidence {actual.confidence:.2f} below expected minimum {expected.confidence_min}"
        )
    if (
        expected.suspected_file_path is not None
        and actual.suspected_file_path != expected.suspected_file_path
    ):
        reasons.append(
            f"suspected_file_path {actual.suspected_file_path!r} != "
            f"expected {expected.suspected_file_path!r}"
        )
    return ScoreResult(passed=not reasons, reasons=reasons)
