"""
Routing Service — wraps the RoadNetwork and RouteOptimizer for use by the API.

Periodically refreshes the road graph with the latest congestion data from
the traffic service so that route recommendations reflect current conditions.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from routing.road_network   import RoadNetwork
from routing.route_optimizer import RouteOptimizer, route_to_dict
from backend.services.traffic_service import get_current_traffic

log = logging.getLogger(__name__)

_REFRESH_INTERVAL_S = int(os.getenv("ROUTE_REFRESH_INTERVAL_S", "30"))


class RoutingService:
    """Singleton-style service that maintains a live road graph."""

    def __init__(self):
        self._network  = RoadNetwork()
        self._optimizer = RouteOptimizer(self._network, max_alternatives=2)
        self._lock     = threading.Lock()
        self._last_refresh: Optional[str] = None

        # Start background refresh thread
        t = threading.Thread(target=self._refresh_loop, daemon=True, name="RouteRefresh")
        t.start()
        log.info("RoutingService initialised; refresh every %ds", _REFRESH_INTERVAL_S)

    # ── Public API ────────────────────────────────────────────────────────────

    def find_routes(self, source: str, destination: str) -> Dict[str, Any]:
        """Return recommended + alternative routes as JSON-safe dicts."""
        with self._lock:
            result = self._optimizer.recommend(source, destination)

        if result.get("error"):
            return result

        return {
            "recommended":      route_to_dict(result["recommended"]),
            "alternatives":     [route_to_dict(r) for r in result["alternatives"]],
            "source_info":      result["source_info"],
            "destination_info": result["destination_info"],
            "error":            None,
            "last_graph_refresh": self._last_refresh,
        }

    def available_nodes(self):
        return self._network.nodes()

    def refresh_congestion(self) -> int:
        """Pull latest traffic data and update the road graph."""
        try:
            traffic = get_current_traffic()
            updates = [
                {
                    "segment_id":       t["segment_id"],
                    "congestion_score": t.get("congestion_score", 0.0),
                    "congestion_level": t.get("congestion_level", "LOW"),
                    "current_speed_kph": t.get("avg_speed_kph"),
                }
                for t in traffic
            ]
            with self._lock:
                count = self._network.bulk_update_congestion(updates)
            from datetime import datetime, timezone
            self._last_refresh = datetime.now(timezone.utc).isoformat()
            log.debug("Road graph refreshed — %d segments updated", count)
            return count
        except Exception as exc:
            log.error("Failed to refresh road graph: %s", exc)
            return 0

    # ── Background refresh ────────────────────────────────────────────────────

    def _refresh_loop(self):
        while True:
            time.sleep(_REFRESH_INTERVAL_S)
            self.refresh_congestion()


# Singleton instance (created once at import time)
routing_service = RoutingService()
