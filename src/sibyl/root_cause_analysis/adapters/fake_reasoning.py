from sibyl.root_cause_analysis.domain.models import RootCauseContext, RootCauseExplanation


class FakeReasoningPort:
    def __init__(self, canned_response: RootCauseExplanation | None = None):
        self._canned_response = canned_response

    async def explain_root_cause(self, context: RootCauseContext) -> RootCauseExplanation:
        if self._canned_response is not None:
            return self._canned_response

        suspected_file_path = context.affected_tests[0] if context.affected_tests else None
        confidence = 0.6 if context.affected_tests else 0.2
        return RootCauseExplanation(
            hypothesis_text=(
                f"Fake hypothesis: {context.test_identifier} likely broke due to changes "
                f"in PR #{context.pr_number}."
            ),
            confidence=confidence,
            suspected_commit_sha=context.head_sha,
            suspected_file_path=suspected_file_path,
            llm_model="fake-reasoning-port",
        )
