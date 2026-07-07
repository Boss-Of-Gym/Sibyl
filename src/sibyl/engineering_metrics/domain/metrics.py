def compute_median(values: list[float]) -> float | None:
    if not values:
        return None

    sorted_values = sorted(values)
    sample_size = len(sorted_values)
    mid = sample_size // 2
    if sample_size % 2 == 1:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2


def compute_ci_success_rate(failed_counts: list[int]) -> float | None:
    if not failed_counts:
        return None
    successful = sum(1 for failed in failed_counts if failed == 0)
    return successful / len(failed_counts)
