MATERIAL_CHANGE_THRESHOLD = 0.05


def compute_flakiness(statuses: list[str]) -> tuple[float, int]:
    decisive = [s for s in statuses if s in ("passed", "failed")]
    sample_size = len(decisive)
    if sample_size == 0:
        return 0.0, 0

    pass_count = sum(1 for s in decisive if s == "passed")
    fail_count = sample_size - pass_count
    score = 2 * min(pass_count, fail_count) / sample_size
    return score, sample_size


def is_material_change(previous_score: float | None, new_score: float) -> bool:
    if previous_score is None:
        return True
    return abs(new_score - previous_score) > MATERIAL_CHANGE_THRESHOLD
