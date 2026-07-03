from sibyl.root_cause_analysis.adapters.fake_reasoning import FakeReasoningPort
from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation

CONTEXT = RootCauseContext(
    repository="acme/widgets",
    test_identifier="tests/test_checkout.py::test_applies_discount",
    commit_sha="sha-1",
    pr_number=7,
    head_sha="sha-1",
    risk_score=0.8,
    affected_tests=["tests/test_checkout.py::test_applies_discount"],
    flakiness_score=0.1,
)


async def test_higher_confidence_when_test_is_a_known_affected_test():
    with_impact = await FakeReasoningPort().explain_root_cause(CONTEXT)
    without_impact = await FakeReasoningPort().explain_root_cause(
        CONTEXT.model_copy(update={"affected_tests": []})
    )

    assert with_impact.confidence > without_impact.confidence


async def test_suspected_commit_sha_is_the_pr_head():
    result = await FakeReasoningPort().explain_root_cause(CONTEXT)

    assert result.suspected_commit_sha == CONTEXT.head_sha


async def test_canned_response_overrides_computed_result():
    canned = RootCauseExplanation(
        hypothesis_text="canned",
        confidence=0.99,
        llm_model="canned-model",
    )

    result = await FakeReasoningPort(canned_response=canned).explain_root_cause(CONTEXT)

    assert result is canned
