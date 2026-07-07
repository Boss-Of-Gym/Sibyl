from eval.models import PrAnalysisExpectation, RootCauseExpectation
from eval.scoring import score_pr_risk_assessment, score_root_cause_explanation
from sibyl.pr_analysis.domain.models import RiskAssessment
from sibyl.root_cause_analysis.domain.models import RootCauseExplanation


def _assessment(**overrides) -> RiskAssessment:
    base = RiskAssessment(score=0.5, rationale="ok", contributing_factors=[], llm_model="test")
    return base.model_copy(update=overrides)


def _explanation(**overrides) -> RootCauseExplanation:
    base = RootCauseExplanation(hypothesis_text="likely cause", confidence=0.5, llm_model="test")
    return base.model_copy(update=overrides)


def test_pr_risk_assessment_within_band_passes():
    expected = PrAnalysisExpectation(score_min=0.4, score_max=0.6)

    result = score_pr_risk_assessment(expected, _assessment(score=0.5))

    assert result.passed is True
    assert result.reasons == []


def test_pr_risk_assessment_outside_band_fails():
    expected = PrAnalysisExpectation(score_min=0.6, score_max=1.0)

    result = score_pr_risk_assessment(expected, _assessment(score=0.2))

    assert result.passed is False
    assert "outside expected band" in result.reasons[0]


def test_pr_risk_assessment_fallback_always_fails():
    expected = PrAnalysisExpectation(score_min=0.0, score_max=1.0)

    result = score_pr_risk_assessment(expected, _assessment(explanation_unavailable=True))

    assert result.passed is False
    assert "explanation_unavailable" in result.reasons[0]


def test_root_cause_confidence_and_file_path_match_passes():
    expected = RootCauseExpectation(confidence_min=0.4, suspected_file_path="src/x.py")

    result = score_root_cause_explanation(
        expected, _explanation(confidence=0.7, suspected_file_path="src/x.py")
    )

    assert result.passed is True


def test_root_cause_low_confidence_fails():
    expected = RootCauseExpectation(confidence_min=0.6)

    result = score_root_cause_explanation(expected, _explanation(confidence=0.3))

    assert result.passed is False
    assert "confidence" in result.reasons[0]


def test_root_cause_wrong_file_path_fails():
    expected = RootCauseExpectation(confidence_min=0.0, suspected_file_path="src/x.py")

    result = score_root_cause_explanation(
        expected, _explanation(confidence=0.9, suspected_file_path="src/y.py")
    )

    assert result.passed is False
    assert "suspected_file_path" in result.reasons[0]


def test_root_cause_no_expected_file_path_skips_that_check():
    expected = RootCauseExpectation(confidence_min=0.0)

    result = score_root_cause_explanation(
        expected, _explanation(confidence=0.1, suspected_file_path="src/anything.py")
    )

    assert result.passed is True
