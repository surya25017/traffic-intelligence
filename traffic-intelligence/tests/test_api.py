"""
API integration tests using FastAPI TestClient (no running server needed).
Run with: pytest tests/test_api.py -v
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch DB_PATH to a temp location before importing the app
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "..", "data", "test_traffic.db")

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestHealthEndpoint:

    def test_health_returns_200(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_contains_status(self):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert "version" in data


class TestTrafficEndpoints:

    def test_current_traffic_returns_list(self):
        resp = client.get("/api/traffic/current")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_segments_endpoint(self):
        resp = client.get("/api/traffic/segments")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_statistics_has_summary(self):
        resp = client.get("/api/traffic/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "by_segment" in data
        assert "congestion_trend" in data

    def test_statistics_summary_fields(self):
        resp = client.get("/api/traffic/statistics")
        summary = resp.json()["summary"]
        assert "total_segments" in summary
        assert "avg_congestion_score" in summary
        assert "avg_speed_kph" in summary

    def test_live_vehicles_default(self):
        resp = client.get("/api/traffic/vehicles/live")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "vehicle_id" in data[0]
        assert "latitude" in data[0]

    def test_live_vehicles_count_param(self):
        resp = client.get("/api/traffic/vehicles/live?count=5")
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_live_vehicles_count_too_high(self):
        resp = client.get("/api/traffic/vehicles/live?count=9999")
        assert resp.status_code == 422   # validation error

    def test_history_endpoint(self):
        resp = client.get("/api/traffic/history?limit=10")
        assert resp.status_code == 200
        assert "records" in resp.json()


class TestRoutesEndpoints:

    def test_nodes_endpoint(self):
        resp = client.get("/api/routes/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert data["count"] >= 10

    def test_recommend_route_valid(self):
        resp = client.post("/api/routes/recommend", json={"source": "A", "destination": "G"})
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended" in data
        assert data["recommended"] is not None
        assert data["error"] is None

    def test_recommend_route_has_segments(self):
        resp = client.post("/api/routes/recommend", json={"source": "A", "destination": "G"})
        route = resp.json()["recommended"]
        assert len(route["segments"]) > 0

    def test_recommend_route_has_alternatives(self):
        resp = client.post("/api/routes/recommend", json={"source": "A", "destination": "G"})
        data = resp.json()
        assert isinstance(data["alternatives"], list)

    def test_recommend_same_node_error(self):
        resp = client.post("/api/routes/recommend", json={"source": "A", "destination": "A"})
        assert resp.status_code == 400

    def test_recommend_invalid_node_error(self):
        resp = client.post("/api/routes/recommend", json={"source": "A", "destination": "ZZZZ"})
        assert resp.status_code == 400

    def test_recommend_missing_field(self):
        resp = client.post("/api/routes/recommend", json={"source": "A"})
        assert resp.status_code == 422   # validation error

    def test_route_response_fields(self):
        resp = client.post("/api/routes/recommend", json={"source": "N", "destination": "B"})
        route = resp.json()["recommended"]
        for field in ["route_id", "source", "destination", "nodes",
                      "total_distance_km", "total_time_min", "avg_congestion_score"]:
            assert field in route, f"Missing field: {field}"

    def test_refresh_endpoint(self):
        resp = client.post("/api/routes/refresh")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
