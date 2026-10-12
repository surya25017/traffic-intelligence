"""
Pydantic models (request/response) for the Traffic Intelligence API.
"""
from __future__ import annotations
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float


class TrafficSegment(BaseModel):
    segment_id:       str
    window_start:     Optional[str] = None
    window_end:       Optional[str] = None
    avg_speed_kph:    Optional[float] = None
    vehicle_count:    Optional[int]   = None
    density:          Optional[float] = None
    congestion_score: float = 0.0
    congestion_level: str  = "UNKNOWN"
    computed_at:      Optional[str]   = None
    color:            str  = "#94a3b8"


class TrafficSummary(BaseModel):
    total_segments:    int
    low_count:         int
    moderate_count:    int
    high_count:        int
    severe_count:      int
    avg_congestion_score: float
    avg_speed_kph:     float
    total_vehicles:    int
    last_updated:      str


class VehiclePosition(BaseModel):
    vehicle_id:      str
    latitude:        float
    longitude:       float
    speed_kph:       float
    heading_degrees: float
    road_segment_id: str
    timestamp:       str


class RouteRequest(BaseModel):
    source:      str = Field(..., description="Source node ID (e.g. 'A')")
    destination: str = Field(..., description="Destination node ID (e.g. 'G')")

    class Config:
        json_schema_extra = {
            "example": {"source": "A", "destination": "G"}
        }


class RouteSegmentInfo(BaseModel):
    segment_id:        str
    from_node:         str
    to_node:           str
    distance_km:       float
    speed_limit_kph:   float
    current_speed_kph: float
    congestion_score:  float
    congestion_level:  str
    travel_time_min:   float
    road_type:         str


class RouteInfo(BaseModel):
    route_id:              str
    source:                str
    destination:           str
    label:                 str
    is_recommended:        bool
    nodes:                 List[str]
    total_distance_km:     float
    total_time_min:        float
    avg_congestion_score:  float
    dominant_level:        str
    segments:              List[RouteSegmentInfo]


class RouteResponse(BaseModel):
    recommended:      Optional[RouteInfo]   = None
    alternatives:     List[RouteInfo]       = []
    source_info:      Optional[dict]        = None
    destination_info: Optional[dict]        = None
    error:            Optional[str]         = None


class HistoryPoint(BaseModel):
    computed_at:      str
    congestion_score: float
    congestion_level: str
    avg_speed_kph:    Optional[float]


class StatisticsResponse(BaseModel):
    summary:         TrafficSummary
    by_segment:      List[TrafficSegment]
    congestion_trend: List[dict]    # [{hour, avg_score}]
