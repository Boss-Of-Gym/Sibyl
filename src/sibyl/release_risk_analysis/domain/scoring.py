def compute_ci_success_rate(failed_counts: list[int]) -> float | None:
    if not failed_counts:
        return None
    successful = sum(1 for failed in failed_counts if failed == 0)
    return successful / len(failed_counts)


def compute_average_coverage_pct(coverage_percentages: list[float]) -> float | None:
    if not coverage_percentages:
        return None
    return sum(coverage_percentages) / len(coverage_percentages)


def compute_release_risk_score(
    regression_probability: float | None,
    ci_success_rate: float | None,
    coverage_pct: float | None,
) -> tuple[float, list[str]]:
    risk_contributions: list[float] = []
    considered_signals: list[str] = []

    if regression_probability is not None:
        risk_contributions.append(regression_probability)
        considered_signals.append("regression_probability")
    if ci_success_rate is not None:
        risk_contributions.append(1 - ci_success_rate)
        considered_signals.append("ci_success_rate")
    if coverage_pct is not None:
        risk_contributions.append(1 - coverage_pct)
        considered_signals.append("coverage_pct")

    if not risk_contributions:
        return 0.0, considered_signals

    return sum(risk_contributions) / len(risk_contributions), considered_signals
