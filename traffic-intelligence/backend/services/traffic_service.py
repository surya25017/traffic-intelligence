"""
Traffic Service — reads congestion data from SQLite (written by the Spark job)
and provides current traffic state to the API.

The SQLite database is the integration point between the Spark streaming job
and the FastAPI backend.  Multiple FastAPI workers can safely read from it
concurrently because SQLite supports concurrent readers.
"""
from __future__ import annotations

import json
import os
import logging
import sqlite3
import random
import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from spark.congestion_processor import congestion_color

log = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/app/data/traffic.db")

# Road segment metadata for enrichment
_SEGMENT_META: Dict[str, dict] = {
    "SEG-AB": {"from": "A", "to": "B", "speed_limit": 60},
    "SEG-AC": {"from": "A", "to": "C", "speed_limit": 60},
    "SEG-AD": {"from": "A", "to": "D", "speed_limit": 50},
    "SEG-AE": {"from": "A", "to": "E", "speed_limit": 50},
    "SEG-BF": {"from": "B", "to": "F", "speed_limit": 60},
    "SEG-CF": {"from": "C", "to": "F", "speed_limit": 70},
    "SEG-CG": {"from": "C", "to": "G", "speed_limit": 60},
    "SEG-DG": {"from": "D", "to": "G", "speed_limit": 50},
    "SEG-DH": {"from": "D", "to": "H", "speed_limit": 50},
    "SEG-EH": {"from": "E", "to": "H", "speed_limit": 50},
    "SEG-EI": {"from": "E", "to": "I", "speed_limit": 60},
    "SEG-NO": {"from": "N", "to": "O", "speed_limit": 80},
    "SEG-OB": {"from": "O", "to": "B", "speed_limit": 60},
    "SEG-NR": {"from": "N", "to": "R", "speed_limit": 70},
    "SEG-PG": {"from": "P", "to": "G", "speed_limit": 60},
    "SEG-QI": {"from": "Q", "to": "I", "speed_limit": 60},
    "SEG-RE": {"from": "R", "to": "E", "speed_limit": 50},
    "SEG-BA": {"from": "B", "to": "A", "speed_limit": 60},
    "SEG-CA": {"from": "C", "to": "A", "speed_limit": 60},
    "SEG-DA": {"from": "D", "to": "A", "speed_limit": 50},
    "SEG-EA": {"from": "E", "to": "A", "speed_limit": 50},
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def get_current_traffic() -> List[dict]:
    """
    Return the most recent congestion record for each segment.
    Falls back to simulated data if the database has no records yet.
    """
    try:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT ch.*
            FROM congestion_history ch
            INNER JOIN (
                SELECT segment_id, MAX(window_end) AS max_end
                FROM congestion_history
                GROUP BY segment_id
            ) latest ON ch.segment_id = latest.segment_id
                      AND ch.window_end = latest.max_end
        """).fetchall()
        conn.close()

        if rows:
            return [_enrich(dict(r)) for r in rows]
    except Exception as exc:
        log.warning("DB read error, using simulated data: %s", exc)

    # Fallback: generate simulated traffic state
    return _simulated_traffic()


def get_traffic_segments() -> List[dict]:
    """Alias for get_current_traffic — returns per-segment data."""
    return get_current_traffic()


def get_statistics() -> dict:
    """Return summary statistics and 24-hour congestion trend."""
    segments = get_current_traffic()

    level_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "SEVERE": 0}
    total_score  = 0.0
    total_speed  = 0.0
    total_veh    = 0
    valid_speed  = 0

    for seg in segments:
        lvl = seg.get("congestion_level", "LOW")
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
        total_score += seg.get("congestion_score", 0.0)
        spd = seg.get("avg_speed_kph")
        if spd:
            total_speed += spd
            valid_speed += 1
        total_veh += seg.get("vehicle_count", 0) or 0

    n = max(len(segments), 1)

    summary = {
        "total_segments":      n,
        "low_count":           level_counts.get("LOW", 0),
        "moderate_count":      level_counts.get("MODERATE", 0),
        "high_count":          level_counts.get("HIGH", 0),
        "severe_count":        level_counts.get("SEVERE", 0),
        "avg_congestion_score": round(total_score / n, 2),
        "avg_speed_kph":       round(total_speed / max(valid_speed, 1), 2),
        "total_vehicles":      total_veh,
        "last_updated":        datetime.now(timezone.utc).isoformat(),
    }

    trend = _congestion_trend()

    return {"summary": summary, "by_segment": segments, "congestion_trend": trend}


def get_history(segment_id: Optional[str] = None, limit: int = 200) -> List[dict]:
    """Return historical congestion records, optionally filtered by segment."""
    try:
        conn = _get_conn()
        if segment_id:
            rows = conn.execute("""
                SELECT * FROM congestion_history
                WHERE segment_id = ?
                ORDER BY window_end DESC LIMIT ?
            """, (segment_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM congestion_history
                ORDER BY window_end DESC LIMIT ?
            """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("History read error: %s", exc)
        return []


# ── Internal helpers ──────────────────────────────────────────────────────────

def _enrich(record: dict) -> dict:
    """Add color and metadata to a raw DB record."""
    record["color"] = congestion_color(record.get("congestion_level", "UNKNOWN"))
    meta = _SEGMENT_META.get(record.get("segment_id", ""), {})
    record["speed_limit_kph"] = meta.get("speed_limit", 50)
    return record


def _simulated_traffic() -> List[dict]:
    """Generate realistic simulated traffic state for demo/fallback mode."""
    now = datetime.now(timezone.utc).isoformat()
    hour = datetime.now().hour
    congestion_base = _hour_congestion(hour)

    result = []
    for seg_id, meta in _SEGMENT_META.items():
        cong = min(1.0, max(0.0, congestion_base + random.gauss(0, 0.12)))
        speed_limit = meta["speed_limit"]
        speed = max(5.0, speed_limit * (1 - cong) + random.gauss(0, 3))
        score = round(cong * 100, 1)

        if score < 25:   level = "LOW"
        elif score < 50: level = "MODERATE"
        elif score < 75: level = "HIGH"
        else:            level = "SEVERE"

        result.append({
            "segment_id":       seg_id,
            "window_start":     now,
            "window_end":       now,
            "avg_speed_kph":    round(speed, 1),
            "vehicle_count":    random.randint(5, 80),
            "density":          round(cong * 60, 1),
            "congestion_score": score,
            "congestion_level": level,
            "computed_at":      now,
            "color":            congestion_color(level),
            "speed_limit_kph":  speed_limit,
            "source":           "simulated_fallback",
        })
    return result


def _hour_congestion(hour: int) -> float:
    profile = {
        0: 0.05, 1: 0.05, 2: 0.05, 3: 0.05, 4: 0.08,
        5: 0.15, 6: 0.40, 7: 0.75, 8: 0.95, 9: 0.80,
        10: 0.60, 11: 0.55, 12: 0.65, 13: 0.60, 14: 0.55,
        15: 0.65, 16: 0.80, 17: 0.95, 18: 0.90, 19: 0.70,
        20: 0.50, 21: 0.35, 22: 0.20, 23: 0.10,
    }
    return profile.get(hour, 0.5)


def _congestion_trend() -> List[dict]:
    """Return a 24-hour simulated congestion trend for charts."""
    trend = []
    for h in range(24):
        base = _hour_congestion(h)
        trend.append({
            "hour":       h,
            "avg_score":  round(base * 100, 1),
            "label":      f"{h:02d}:00",
        })
    return trend
