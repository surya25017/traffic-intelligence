"""
Road Network — loads the sample road network from JSON and builds a
weighted directed NetworkX graph.

The graph can be updated at runtime with real-time congestion data
so that the route optimizer always uses current travel costs.
"""
from __future__ import annotations

import json
import math
import os
import logging
from typing import Dict, List, Optional, Tuple

import networkx as nx

log = logging.getLogger(__name__)

_DEFAULT_NETWORK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "sample_road_network.json",
)

# Free-flow travel time (minutes) = distance / speed_limit * 60
# Congested travel time adds a penalty multiplier based on congestion score.


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class RoadNetwork:
    """
    Directed weighted graph of the city road network.

    Node attributes: id, name, lat, lon
    Edge attributes: segment_id, distance_km, speed_limit_kph, road_type,
                     current_speed_kph, congestion_score, travel_time_min
    """

    def __init__(self, network_path: str = _DEFAULT_NETWORK_PATH):
        self._graph: nx.DiGraph = nx.DiGraph()
        self._node_lookup: Dict[str, dict] = {}   # node_id → node data
        self._segment_to_edge: Dict[str, Tuple[str, str]] = {}   # segment_id → (u, v)
        self._load(network_path)

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load(self, path: str) -> None:
        with open(path, "r") as fh:
            data = json.load(fh)

        for node in data["nodes"]:
            self._graph.add_node(node["id"], **node)
            self._node_lookup[node["id"]] = node

        for edge in data["edges"]:
            u, v = edge["from"], edge["to"]
            speed_limit = edge.get("speed_limit_kph", 50.0)

            # Verify node positions so we can compute haversine if needed
            if u in self._node_lookup and v in self._node_lookup:
                n_u = self._node_lookup[u]
                n_v = self._node_lookup[v]
                dist = _haversine_km(n_u["lat"], n_u["lon"], n_v["lat"], n_v["lon"])
            else:
                dist = edge.get("distance_km", 1.0)

            # Free-flow travel time in minutes
            ff_time = (dist / max(speed_limit, 1.0)) * 60.0

            self._graph.add_edge(u, v,
                segment_id=edge["id"],
                distance_km=round(dist, 3),
                speed_limit_kph=speed_limit,
                current_speed_kph=speed_limit,   # start at free-flow
                congestion_score=0.0,
                congestion_level="LOW",
                road_type=edge.get("road_type", "local"),
                travel_time_min=round(ff_time, 3),
                lanes=edge.get("lanes", 2),
            )
            self._segment_to_edge[edge["id"]] = (u, v)

        log.info("Road network loaded: %d nodes, %d edges",
                 self._graph.number_of_nodes(), self._graph.number_of_edges())

    # ── Graph access ──────────────────────────────────────────────────────────

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def nodes(self) -> List[dict]:
        return [{"id": nid, **data} for nid, data in self._graph.nodes(data=True)]

    def edges(self) -> List[dict]:
        return [
            {"from": u, "to": v, **data}
            for u, v, data in self._graph.edges(data=True)
        ]

    def node_ids(self) -> List[str]:
        return list(self._graph.nodes())

    def get_node(self, node_id: str) -> Optional[dict]:
        return self._node_lookup.get(node_id)

    def get_edge_by_segment(self, segment_id: str) -> Optional[dict]:
        edge = self._segment_to_edge.get(segment_id)
        if edge:
            u, v = edge
            return dict(self._graph[u][v])
        return None

    # ── Congestion updates ────────────────────────────────────────────────────

    def update_congestion(self, segment_id: str, congestion_score: float,
                          congestion_level: str, current_speed_kph: Optional[float] = None) -> bool:
        """
        Update a road segment with fresh congestion data.
        Recalculates travel_time_min using a Bureau of Public Roads (BPR) penalty:
            t = t0 * (1 + 0.15 * (v/c)^4)
        We approximate (v/c) from the congestion score.

        Returns True if the segment was found and updated.
        """
        edge = self._segment_to_edge.get(segment_id)
        if not edge:
            return False

        u, v = edge
        attrs = self._graph[u][v]

        speed_limit = attrs["speed_limit_kph"]
        distance    = attrs["distance_km"]

        # Derive effective current speed
        if current_speed_kph is not None and current_speed_kph > 0:
            eff_speed = current_speed_kph
        else:
            # Estimate from congestion score: score 0→speed_limit, score 100→5 kph
            eff_speed = max(5.0, speed_limit * (1.0 - congestion_score / 100.0))

        ff_time = (distance / max(speed_limit, 1.0)) * 60.0
        travel_time = (distance / max(eff_speed, 1.0)) * 60.0

        # Add BPR-inspired penalty for high congestion
        volume_capacity_ratio = congestion_score / 100.0
        bpr_factor = 1.0 + 0.15 * (volume_capacity_ratio ** 4)
        travel_time *= bpr_factor

        self._graph[u][v].update({
            "current_speed_kph": round(eff_speed, 1),
            "congestion_score":  round(congestion_score, 2),
            "congestion_level":  congestion_level,
            "travel_time_min":   round(travel_time, 3),
        })
        return True

    def bulk_update_congestion(self, updates: List[dict]) -> int:
        """
        Apply a list of congestion updates.
        Each dict must have keys: segment_id, congestion_score, congestion_level.
        Optionally: current_speed_kph.
        Returns the count of successfully updated segments.
        """
        count = 0
        for upd in updates:
            ok = self.update_congestion(
                segment_id=upd["segment_id"],
                congestion_score=upd.get("congestion_score", 0.0),
                congestion_level=upd.get("congestion_level", "LOW"),
                current_speed_kph=upd.get("current_speed_kph"),
            )
            if ok:
                count += 1
        log.debug("Bulk congestion update applied to %d/%d segments", count, len(updates))
        return count
