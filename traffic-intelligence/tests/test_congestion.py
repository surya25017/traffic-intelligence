"""
Tests for congestion scoring and classification.
Run with: pytest tests/test_congestion.py -v
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spark.congestion_processor import (
    SegmentInput, calculate_congestion_score, classify_congestion, congestion_color,
)


def _make_input(**kwargs):
    defaults = dict(
        segment_id="SEG-TEST",
        avg_speed_kph=50.0,
        speed_limit_kph=60.0,
        vehicle_count=20,
        road_capacity_vph=2400.0,
        density_veh_per_km=10.0,
    )
    defaults.update(kwargs)
    return SegmentInput(**defaults)


class TestCongestionScore:

    def test_free_flow_score_is_low(self):
        """Free-flow conditions should produce a LOW score."""
        inp = _make_input(avg_speed_kph=58.0, vehicle_count=5, density_veh_per_km=2.0)
        result = calculate_congestion_score(inp)
        assert result.congestion_score < 25, f"Expected LOW, got {result.congestion_score}"
        assert result.congestion_level == "LOW"

    def test_gridlock_score_is_severe(self):
        """Near-stationary traffic with high density should be SEVERE."""
        inp = _make_input(avg_speed_kph=5.0, vehicle_count=2000, density_veh_per_km=100.0)
        result = calculate_congestion_score(inp)
        assert result.congestion_score >= 75, f"Expected SEVERE, got {result.congestion_score}"
        assert result.congestion_level == "SEVERE"

    def test_moderate_congestion(self):
        """Moderate slowdown should produce MODERATE level."""
        inp = _make_input(avg_speed_kph=35.0, vehicle_count=900, density_veh_per_km=30.0)
        result = calculate_congestion_score(inp)
        assert result.congestion_level in ("MODERATE", "HIGH"), result.congestion_level

    def test_score_bounded_0_to_100(self):
        """Score must always be between 0 and 100."""
        for spd in [0, 5, 30, 60, 200]:
            inp = _make_input(avg_speed_kph=spd)
            result = calculate_congestion_score(inp)
            assert 0.0 <= result.congestion_score <= 100.0

    def test_missing_speed_penalised(self):
        """None speed should produce a higher score than free-flow."""
        free  = calculate_congestion_score(_make_input(avg_speed_kph=60.0))
        nosp  = calculate_congestion_score(_make_input(avg_speed_kph=None))
        assert nosp.congestion_score > free.congestion_score

    def test_zero_speed_handled_safely(self):
        """Speed of 0 should not raise an exception."""
        inp = _make_input(avg_speed_kph=0.0)
        result = calculate_congestion_score(inp)
        assert result.congestion_score >= 0

    def test_missing_capacity_does_not_crash(self):
        """None capacity should skip the volume component without error."""
        inp = _make_input(road_capacity_vph=None)
        result = calculate_congestion_score(inp)
        assert result.congestion_score >= 0

    def test_missing_density_does_not_crash(self):
        """None density should skip the density component without error."""
        inp = _make_input(density_veh_per_km=None)
        result = calculate_congestion_score(inp)
        assert result.congestion_score >= 0


class TestClassification:

    @pytest.mark.parametrize("score,expected", [
        (0,   "LOW"),
        (24,  "LOW"),
        (25,  "MODERATE"),
        (49,  "MODERATE"),
        (50,  "HIGH"),
        (74,  "HIGH"),
        (75,  "SEVERE"),
        (100, "SEVERE"),
    ])
    def test_classify_thresholds(self, score, expected):
        assert classify_congestion(score) == expected


class TestCongestionColor:

    def test_colors_match_level(self):
        assert congestion_color("LOW")      == "#22c55e"
        assert congestion_color("MODERATE") == "#eab308"
        assert congestion_color("HIGH")     == "#f97316"
        assert congestion_color("SEVERE")   == "#ef4444"
        assert congestion_color("UNKNOWN")  == "#94a3b8"


class TestCongestionAffectsRoute:
    """
    Demonstrates that increasing congestion on a segment raises its travel cost,
    which should cause the router to prefer an alternative path.
    """

    def test_congestion_raises_score(self):
        """A segment with high congestion should score higher than free-flow."""
        free  = calculate_congestion_score(_make_input(avg_speed_kph=60.0, density_veh_per_km=2.0, vehicle_count=10))
        cong  = calculate_congestion_score(_make_input(avg_speed_kph=10.0, density_veh_per_km=90.0, vehicle_count=1800))
        assert cong.congestion_score > free.congestion_score

    def test_congested_segment_is_severe(self):
        inp = _make_input(avg_speed_kph=6.0, vehicle_count=2100, density_veh_per_km=110.0)
        result = calculate_congestion_score(inp)
        assert result.congestion_level == "SEVERE"
