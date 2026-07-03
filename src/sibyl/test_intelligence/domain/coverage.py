def compute_coverage_pct(lines_covered: int, lines_total: int) -> float:
    if lines_total == 0:
        return 0.0
    return lines_covered / lines_total
