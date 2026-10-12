"""
Route Optimizer — congestion-aware shortest-path engine built on NetworkX.

Uses Dijkstra's algorithm with travel_time_min as the edge weight.
Returns the primary recommended route and up to 2 alternative routes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

import networkx as nx

from routing.road_network import RoadNetwork

log = logging.getLogger(__name__)


@dataclass
class RouteSegment:
    """One road segment within a computed route."""
    segment_id:       str
    from_node:        str
    to_node:          str
    distance_km:      float
    speed_limit_kph:  float
    current_speed_kph: float
    congestion_score: float
    congestion_level: str
    travel_time_min:  float
    road_type:        str


@dataclass
class Route:
    """A complete route from source to destination."""
    route_id:            str
    source:              str
    destination:         str
    nodes:               List[str]
    segments:            List[RouteSegment]
    total_distance_km:   float
    total_time_min:      float
    avg_congestion_score: float
    dominant_level:      str
    is_recommended:      bool = False
    label:               str = ""


class RouteOptimizer:
    """
    Congestion-aware route recommendation engine.

    The cost function is travel_time_min on each edge.  High-congestion edges
    carry a BPR-inflated travel time (applied in RoadNetwork.update_congestion).

    Finds the k-shortest simple paths using Yen's algorithm and returns the
    top-k after filtering duplicates.
    """

    def __init__(self, road_network: RoadNetwork, max_alternatives: int = 2):
        self._net = road_network
        self._max_alt = max_alternatives

    # ── Public API ────────────────────────────────────────────────────────────

    def recommend(self, source: str, destination: str) -> Dict[str, Any]:
        """
        Find the recommended route and alternatives.

        Returns a dict with keys:
          - recommended: Route
          - alternatives: List[Route]
          - source_info: dict
          - destination_info: dict
          - error: str or None
        """
        result: Dict[str, Any] = {
            "recommended":   None,
            "alternatives":  [],
            "source_info":   self._net.get_node(source),
            "destination_info": self._net.get_node(destination),
            "error":         None,
        }

        g = self._net.graph

        if source not in g:
            result["error"] = f"Source node '{source}' not found in road network."
            return result
        if destination not in g:
            result["error"] = f"Destination node '{destination}' not found in road network."
            return result
        if source == destination:
            result["error"] = "Source and destination must be different."
            return result

        if not nx.has_path(g, source, destination):
            result["error"] = f"No path exists between '{source}' and '{destination}'."
            return result

        try:
            # Yen's k-shortest simple paths
            k_paths = list(nx.shortest_simple_paths(
                g, source, destination, weight="travel_time_min"
            ))
        except nx.NetworkXNoPath:
            result["error"] = "No path found."
            return result

        routes: List[Route] = []
        for idx, path in enumerate(k_paths[:self._max_alt + 1]):
            route = self._build_route(
                route_id=f"ROUTE-{idx+1}",
                path=path,
                source=source,
                destination=destination,
                is_recommended=(idx == 0),
                label="Recommended" if idx == 0 else f"Alternative {idx}",
            )
            routes.append(route)

        if not routes:
            result["error"] = "Could not build any route."
            return result

        result["recommended"]  = routes[0]
        result["alternatives"] = routes[1:]
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_route(self, route_id: str, path: List[str],
                     source: str, destination: str,
                     is_recommended: bool, label: str) -> Route:
        g = self._net.graph
        segments: List[RouteSegment] = []
        total_dist = 0.0
        total_time = 0.0
        score_sum  = 0.0

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            data = g[u][v]
            seg = RouteSegment(
                segment_id=data.get("segment_id", f"{u}-{v}"),
                from_node=u,
                to_node=v,
                distance_km=data.get("distance_km", 0.0),
                speed_limit_kph=data.get("speed_limit_kph", 50.0),
                current_speed_kph=data.get("current_speed_kph", 50.0),
                congestion_score=data.get("congestion_score", 0.0),
                congestion_level=data.get("congestion_level", "LOW"),
                travel_time_min=data.get("travel_time_min", 0.0),
                road_type=data.get("road_type", "local"),
            )
            segments.append(seg)
            total_dist += seg.distance_km
            total_time += seg.travel_time_min
            score_sum  += seg.congestion_score

        avg_score = score_sum / max(len(segments), 1)
        dominant  = self._dominant_level(segments)

        return Route(
            route_id=route_id,
            source=source,
            destination=destination,
            nodes=path,
            segments=segments,
            total_distance_km=round(total_dist, 3),
            total_time_min=round(total_time, 2),
            avg_congestion_score=round(avg_score, 2),
            dominant_level=dominant,
            is_recommended=is_recommended,
            label=label,
        )

    @staticmethod
    def _dominant_level(segments: List[RouteSegment]) -> str:
        level_map = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "SEVERE": 3}
        if not segments:
            return "UNKNOWN"
        worst = max(segments, key=lambda s: level_map.get(s.congestion_level, 0))
        return worst.congestion_level


def route_to_dict(route: Optional[Route]) -> Optional[dict]:
    """Serialise a Route to a JSON-safe dict for the API response."""
    if route is None:
        return None
    return {
        "route_id":            route.route_id,
        "source":              route.source,
        "destination":         route.destination,
        "label":               route.label,
        "is_recommended":      route.is_recommended,
        "nodes":               route.nodes,
        "total_distance_km":   route.total_distance_km,
        "total_time_min":      route.total_time_min,
        "avg_congestion_score": route.avg_congestion_score,
        "dominant_level":      route.dominant_level,
        "segments": [
            {
                "segment_id":       s.segment_id,
                "from_node":        s.from_node,
                "to_node":          s.to_node,
                "distance_km":      s.distance_km,
                "speed_limit_kph":  s.speed_limit_kph,
                "current_speed_kph": s.current_speed_kph,
                "congestion_score": s.congestion_score,
                "congestion_level": s.congestion_level,
                "travel_time_min":  s.travel_time_min,
                "road_type":        s.road_type,
            }
            for s in route.segments
        ],
    }
