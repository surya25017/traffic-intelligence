"""
Congestion Processor — pure-Python congestion scoring logic.

Designed to be used both:
  1. Inside the Spark streaming job (via UDFs).
  2. Standalone for unit testing (no Spark dependency required).

Calibration note
----------------
The thresholds below were chosen to produce meaningful classifications for the
simulated data.  In a production deployment you would calibrate them using
historical speed and flow data from the actual road network, typically by
comparing observed mean speeds against free-flow speeds measured at low-demand
times of day.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# ── Configurable thresholds (override via env vars) ───────────────────────────
_LOW_THRESHOLD      = float(os.getenv("CONGESTION_LOW_THRESHOLD",      "25"))
_MODERATE_THRESHOLD = float(os.getenv("CONGESTION_MODERATE_THRESHOLD", "50"))
_HIGH_THRESHOLD     = float(os.getenv("CONGESTION_HIGH_THRESHOLD",     "75"))


@dataclass
class SegmentInput:
    """Aggregated metrics for one road segment over a time window."""
    segment_id:        str
    avg_speed_kph:     Optional[float]
    speed_limit_kph:   float
    vehicle_count:     Optional[int]
    road_capacity_vph: Optional[float]
    density_veh_per_km: Optional[float]


@dataclass
class CongestionResult:
    """Output of the congestion scorer for one segment."""
    segment_id:       str
    congestion_score: float          # 0–100
    congestion_level: str            # LOW | MODERATE | HIGH | SEVERE
    speed_ratio:      float          # avg_speed / speed_limit
    volume_ratio:     float          # vehicle_count / capacity
    density_score:    float          # normalised density contribution
    details:          dict = field(default_factory=dict)


# ── Scoring formula ───────────────────────────────────────────────────────────
# score = 100 * (
#     w_speed   * (1 - speed_ratio)   +
#     w_volume  * volume_ratio        +
#     w_density * density_score
# )
# Weights must sum to 1.0.
_W_SPEED   = 0.50
_W_VOLUME  = 0.30
_W_DENSITY = 0.20

_JAM_DENSITY_VEH_KM = 120.0   # typical jam density on a 2-lane road


def calculate_congestion_score(inp: SegmentInput) -> CongestionResult:
    """
    Compute a 0–100 congestion score and classify it.

    Handles missing inputs gracefully:
    - If avg_speed is None/0, speed component is penalised fully.
    - If capacity is unknown, volume component is skipped (weight redistributed).
    - If density is unknown, density component is skipped.
    """
    # ── Speed component (0 = free-flow, 1 = stationary) ──────────────────────
    speed_limit = max(inp.speed_limit_kph, 1.0)

    if inp.avg_speed_kph is None or inp.avg_speed_kph <= 0:
        speed_ratio   = 0.0      # unknown → assume stationary
        speed_penalty = 1.0
        log.debug("Segment %s: speed unavailable, using full penalty", inp.segment_id)
    else:
        speed_ratio   = min(inp.avg_speed_kph / speed_limit, 1.0)
        speed_penalty = 1.0 - speed_ratio

    # ── Volume component (0 = empty, 1 = at or above capacity) ───────────────
    if inp.vehicle_count is not None and inp.road_capacity_vph and inp.road_capacity_vph > 0:
        volume_ratio = min(inp.vehicle_count / inp.road_capacity_vph, 1.0)
    else:
        volume_ratio = 0.0

    # ── Density component ─────────────────────────────────────────────────────
    if inp.density_veh_per_km is not None and inp.density_veh_per_km >= 0:
        density_score = min(inp.density_veh_per_km / _JAM_DENSITY_VEH_KM, 1.0)
    else:
        density_score = 0.0

    # ── Weighted score ────────────────────────────────────────────────────────
    raw_score = (
        _W_SPEED   * speed_penalty +
        _W_VOLUME  * volume_ratio  +
        _W_DENSITY * density_score
    )
    congestion_score = round(min(100.0, max(0.0, raw_score * 100)), 2)

    level = classify_congestion(congestion_score)

    return CongestionResult(
        segment_id=inp.segment_id,
        congestion_score=congestion_score,
        congestion_level=level,
        speed_ratio=round(speed_ratio, 4),
        volume_ratio=round(volume_ratio, 4),
        density_score=round(density_score, 4),
        details={
            "speed_penalty":  round(speed_penalty, 4),
            "speed_weight":   _W_SPEED,
            "volume_weight":  _W_VOLUME,
            "density_weight": _W_DENSITY,
        },
    )


def classify_congestion(score: float) -> str:
    """
    Map a 0–100 score to a congestion level.
    Thresholds are configurable via environment variables.
    """
    if score < _LOW_THRESHOLD:
        return "LOW"
    elif score < _MODERATE_THRESHOLD:
        return "MODERATE"
    elif score < _HIGH_THRESHOLD:
        return "HIGH"
    else:
        return "SEVERE"


def congestion_color(level: str) -> str:
    """Map level to a CSS/Leaflet color string for the frontend."""
    return {
        "LOW":      "#22c55e",   # green
        "MODERATE": "#eab308",   # yellow
        "HIGH":     "#f97316",   # orange
        "SEVERE":   "#ef4444",   # red
    }.get(level, "#94a3b8")
