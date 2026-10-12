"""
Tests for the road network graph and route optimizer.
Run with: pytest tests/test_routing.py -v
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routing.road_network    import RoadNetwork
from routing.route_optimizer import RouteOptimizer, route_to_dict


@pytest.fixture(scope="module")
def network():
    return RoadNetwork()


@pytest.fixture(scope="module")
def optimizer(network):
    return RouteOptimizer(network, max_alternatives=2)


class TestRoadNetwork:

    def test_loads_nodes(self, network):
        nodes = network.nodes()
        assert len(nodes) >= 10, "Expected at least 10 nodes"

    def test_loads_edges(self, network):
        edges = network.edges()
        assert len(edges) >= 10, "Expected at least 10 edges"

    def test_node_has_coordinates(self, network):
        node_a = network.get_node("A")
        assert node_a is not None
        assert "lat" in node_a and "lon" in node_a

    def test_edge_has_travel_time(self, network):
        edges = network.edges()
        for e in edges:
            assert "travel_time_min" in e, f"Edge missing travel_time_min: {e}"
            assert e["travel_time_min"] > 0

    def test_congestion_update(self, network):
        ok = network.update_congestion("SEG-AB", congestion_score=80.0, congestion_level="SEVERE")
        assert ok is True
        edge = network.get_edge_by_segment("SEG-AB")
        assert edge["congestion_score"] == 80.0
        assert edge["congestion_level"] == "SEVERE"

    def test_unknown_segment_returns_false(self, network):
        ok = network.update_congestion("SEG-NONEXISTENT", 50.0, "HIGH")
        assert ok is False

    def test_bulk_update(self, network):
        updates = [
            {"segment_id": "SEG-AC", "congestion_score": 60.0, "congestion_level": "HIGH"},
            {"segment_id": "SEG-AD", "congestion_score": 10.0, "congestion_level": "LOW"},
        ]
        count = network.bulk_update_congestion(updates)
        assert count == 2


class TestRouteOptimizer:

    def test_basic_route_found(self, optimizer):
        result = optimizer.recommend("A", "G")
        assert result["error"] is None
        assert result["recommended"] is not None

    def test_recommended_route_connects_source_dest(self, optimizer):
        result = optimizer.recommend("A", "G")
        route  = result["recommended"]
        assert route.nodes[0] == "A"
        assert route.nodes[-1] == "G"

    def test_route_has_positive_distance(self, optimizer):
        result = optimizer.recommend("N", "B")
        assert result["recommended"].total_distance_km > 0

    def test_route_has_positive_time(self, optimizer):
        result = optimizer.recommend("A", "F")
        assert result["recommended"].total_time_min > 0

    def test_alternatives_returned(self, optimizer):
        result = optimizer.recommend("A", "G")
        assert len(result["alternatives"]) >= 1

    def test_same_source_destination_error(self, optimizer):
        result = optimizer.recommend("A", "A")
        assert result["error"] is not None

    def test_invalid_node_error(self, optimizer):
        result = optimizer.recommend("A", "ZZZZ")
        assert result["error"] is not None

    def test_route_to_dict_serialisable(self, optimizer):
        result = optimizer.recommend("A", "G")
        d = route_to_dict(result["recommended"])
        assert isinstance(d, dict)
        assert "total_time_min" in d
        assert "segments" in d
        import json
        json.dumps(d)   # must not raise

    def test_congested_route_has_higher_time(self, network, optimizer):
        """
        After marking SEG-AB as SEVERE, the travel time for that segment should
        be higher than free-flow, making the router prefer an alternative if possible.
        """
        # Baseline route A→B
        result_free = optimizer.recommend("A", "B")
        base_time   = result_free["recommended"].total_time_min

        # Apply severe congestion to SEG-AB
        network.update_congestion("SEG-AB", congestion_score=95.0,
                                  congestion_level="SEVERE", current_speed_kph=5.0)

        result_cong = optimizer.recommend("A", "B")
        new_time    = result_cong["recommended"].total_time_min

        # Either the travel time increased (same route, congested) or a different route was chosen
        assert new_time >= base_time or result_cong["recommended"].nodes != result_free["recommended"].nodes, \
            "Congestion should increase travel time or trigger an alternative route"
