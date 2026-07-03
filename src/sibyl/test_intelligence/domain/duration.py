def compute_median_duration(durations_ms: list[int]) -> tuple[float, int]:
    sample_size = len(durations_ms)
    if sample_size == 0:
        return 0.0, 0

    sorted_durations = sorted(durations_ms)
    mid = sample_size // 2
    if sample_size % 2 == 1:
        median = float(sorted_durations[mid])
    else:
        median = (sorted_durations[mid - 1] + sorted_durations[mid]) / 2
    return median, sample_size
