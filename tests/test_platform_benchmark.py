"""Validate overlap accounting, including touching and failed intervals."""

from agenteval.platform_benchmark import overlap


def test_overlap_counts_actual_intervals_not_configured_workers():
    assert overlap([]) == 0
    assert overlap([(0, 1), (1, 2)]) == 1
    assert overlap([(0, 3), (1, 2), (1.5, 4), (5, 6)]) == 3
