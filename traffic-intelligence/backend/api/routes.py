"""
Routes API router — /api/routes/* endpoints.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.models.schemas  import RouteRequest, RouteResponse
from backend.services.routing_service import routing_service

router = APIRouter(prefix="/api/routes", tags=["Routes"])
log    = logging.getLogger(__name__)


@router.post("/recommend", response_model=RouteResponse, summary="Recommend best route")
async def recommend_route(request: RouteRequest):
    """
    Accept a source and destination node ID.
    Returns the best (fastest, congestion-aware) route and up to 2 alternatives.

    Node IDs are letters A–R corresponding to named city locations.
    Use GET /api/routes/nodes to see the full list.
    """
    result = routing_service.find_routes(request.source, request.destination)

    if result.get("error") and not result.get("recommended"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/nodes", summary="Available route nodes")
async def list_nodes():
    """Return all available nodes (locations) in the road network."""
    nodes = routing_service.available_nodes()
    return {"nodes": nodes, "count": len(nodes)}


@router.post("/refresh", summary="Refresh road graph congestion")
async def refresh_graph():
    """
    Trigger an immediate congestion refresh of the road graph.
    Called automatically in the background every 30 seconds.
    """
    count = routing_service.refresh_congestion()
    return {"updated_segments": count, "status": "ok"}
