"""
Traffic API router — /api/traffic/* endpoints.
"""
from __future__ import annotations

import logging
import random
import math
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.models.schemas import (
    TrafficSegment, TrafficSummary, StatisticsResponse, VehiclePosition,
)
from backend.services.traffic_service import (
    get_current_traffic, get_traffic_segments, get_statistics, get_history,
)

router = APIRouter(prefix="/api/traffic", tags=["Traffic"])
log    = logging.getLogger(__name__)

# Simulated vehicle state (refreshed each request for demo)
_VEHICLE_SEGMENTS = [
    {"seg": "SEG-AB", "lat": 28.6139, "lon": 77.2090, "dlat":  0.0001, "dlon":  0.0},
    {"seg": "SEG-AC", "lat": 28.6139, "lon": 77.2090, "dlat":  0.0,    "dlon":  0.0001},
    {"seg": "SEG-CF", "lat": 28.6139, "lon": 77.2200, "dlat":  0.0001, "dlon":  0.0},
    {"seg": "SEG-NO", "lat": 28.5580, "lon": 77.0900, "dlat":  0.0002, "dlon":  0.0003},
    {"seg": "SEG-OB", "lat": 28.6420, "lon": 77.2190, "dlat": -0.0001, "dlon": -0.0001},
]


@router.get("/current", response_model=List[TrafficSegment], summary="Current traffic conditions")
async def current_traffic():
    """Return the latest congestion state for every monitored road segment."""
    data = get_current_traffic()
    return data


@router.get("/segments", response_model=List[TrafficSegment], summary="Road segment congestion")
async def traffic_segments():
    """Return congestion data per road segment."""
    data = get_traffic_segments()
    return data


@router.get("/statistics", response_model=StatisticsResponse, summary="Traffic analytics")
async def traffic_statistics():
    """Return aggregate traffic statistics and a 24-hour trend."""
    stats = get_statistics()
    return stats


@router.get("/history", summary="Historical congestion records")
async def traffic_history(
    segment_id: str = Query(None, description="Filter by segment ID"),
    limit:      int = Query(100,  description="Maximum records to return"),
):
    """Return historical congestion records from the database."""
    records = get_history(segment_id=segment_id, limit=limit)
    return {"records": records, "count": len(records)}


@router.get("/vehicles/live", response_model=List[VehiclePosition], summary="Simulated vehicle positions")
async def live_vehicles(count: int = Query(20, ge=1, le=100)):
    """
    Return simulated vehicle positions.
    NOTE: These are generated positions for demonstration only —
          they are not from real GPS devices.
    """
    now = datetime.now(timezone.utc).isoformat()
    positions = []
    for i in range(count):
        base = _VEHICLE_SEGMENTS[i % len(_VEHICLE_SEGMENTS)]
        # Add random scatter around segment midpoint
        jitter_lat = random.gauss(0, 0.003)
        jitter_lon = random.gauss(0, 0.003)
        positions.append(VehiclePosition(
            vehicle_id=f"VEH-{i+1:04d}",
            latitude=round(base["lat"] + jitter_lat, 6),
            longitude=round(base["lon"] + jitter_lon, 6),
            speed_kph=round(random.uniform(10, 80), 1),
            heading_degrees=round(random.uniform(0, 360), 1),
            road_segment_id=base["seg"],
            timestamp=now,
        ))
    return positions
