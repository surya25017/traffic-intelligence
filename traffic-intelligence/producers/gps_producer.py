"""
GPS Producer — continuously simulates vehicle GPS events and publishes to 'gps-events' Kafka topic.

Each event represents one GPS ping from a vehicle navigating the city road network.
Data is SIMULATED — not from real devices.
"""
import os
import json
import time
import math
import random
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Tuple

from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [GPS-PRODUCER] %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP   = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GPS_TOPIC         = os.getenv("GPS_TOPIC", "gps-events")
NUM_VEHICLES      = int(os.getenv("NUM_VEHICLES", "30"))
PUBLISH_INTERVAL  = float(os.getenv("GPS_PUBLISH_INTERVAL_S", "2.0"))   # seconds between batches
SPEED_NOISE_KPH   = 5.0   # ±noise added to segment speed


# ── Road segments and their realistic speed profiles ──────────────────────────
ROAD_SEGMENTS: List[dict] = [
    {"id": "SEG-AB", "from_lat": 28.6139, "from_lon": 77.2090, "to_lat": 28.6250, "to_lon": 77.2090, "speed_limit": 60, "base_flow_speed": 55},
    {"id": "SEG-AC", "from_lat": 28.6139, "from_lon": 77.2090, "to_lat": 28.6139, "to_lon": 77.2200, "speed_limit": 60, "base_flow_speed": 50},
    {"id": "SEG-AD", "from_lat": 28.6139, "from_lon": 77.2090, "to_lat": 28.6020, "to_lon": 77.2090, "speed_limit": 50, "base_flow_speed": 42},
    {"id": "SEG-AE", "from_lat": 28.6139, "from_lon": 77.2090, "to_lat": 28.6139, "to_lon": 77.1980, "speed_limit": 50, "base_flow_speed": 45},
    {"id": "SEG-BF", "from_lat": 28.6250, "from_lon": 77.2090, "to_lat": 28.6270, "to_lon": 77.2200, "speed_limit": 60, "base_flow_speed": 48},
    {"id": "SEG-CF", "from_lat": 28.6139, "from_lon": 77.2200, "to_lat": 28.6270, "to_lon": 77.2200, "speed_limit": 70, "base_flow_speed": 65},
    {"id": "SEG-CG", "from_lat": 28.6139, "from_lon": 77.2200, "to_lat": 28.5970, "to_lon": 77.2200, "speed_limit": 60, "base_flow_speed": 52},
    {"id": "SEG-DG", "from_lat": 28.6020, "from_lon": 77.2090, "to_lat": 28.5970, "to_lon": 77.2200, "speed_limit": 50, "base_flow_speed": 38},
    {"id": "SEG-DH", "from_lat": 28.6020, "from_lon": 77.2090, "to_lat": 28.5970, "to_lon": 77.1980, "speed_limit": 50, "base_flow_speed": 40},
    {"id": "SEG-EH", "from_lat": 28.6139, "from_lon": 77.1980, "to_lat": 28.5970, "to_lon": 77.1980, "speed_limit": 50, "base_flow_speed": 44},
    {"id": "SEG-EI", "from_lat": 28.6139, "from_lon": 77.1980, "to_lat": 28.6270, "to_lon": 77.1980, "speed_limit": 60, "base_flow_speed": 55},
    {"id": "SEG-NO", "from_lat": 28.5580, "from_lon": 77.0900, "to_lat": 28.6420, "to_lon": 77.2190, "speed_limit": 80, "base_flow_speed": 75},
    {"id": "SEG-OB", "from_lat": 28.6420, "from_lon": 77.2190, "to_lat": 28.6250, "to_lon": 77.2090, "speed_limit": 60, "base_flow_speed": 50},
]


@dataclass
class GPSEvent:
    event_id:         str
    vehicle_id:       str
    latitude:         float
    longitude:        float
    speed_kph:        float
    heading_degrees:  float
    road_segment_id:  str
    timestamp:        str
    event_type:       str = "gps_ping"
    source:           str = "simulated"


class VehicleSimulator:
    """Simulates a single vehicle moving along road segments."""

    def __init__(self, vehicle_id: str):
        self.vehicle_id = vehicle_id
        self.segment = random.choice(ROAD_SEGMENTS)
        self.progress = random.random()   # 0.0 → 1.0 along current segment
        # Each vehicle carries a congestion multiplier (simulates rush-hour slowdowns)
        self.congestion_factor = random.uniform(0.4, 1.0)

    def _interpolate_position(self) -> Tuple[float, float]:
        seg = self.segment
        lat = seg["from_lat"] + self.progress * (seg["to_lat"] - seg["from_lat"])
        lon = seg["from_lon"] + self.progress * (seg["to_lon"] - seg["from_lon"])
        return round(lat, 6), round(lon, 6)

    def _heading(self) -> float:
        seg = self.segment
        dlat = seg["to_lat"] - seg["from_lat"]
        dlon = seg["to_lon"] - seg["from_lon"]
        return round(math.degrees(math.atan2(dlon, dlat)) % 360, 1)

    def next_event(self) -> GPSEvent:
        """Advance vehicle and return a GPS event."""
        seg = self.segment
        base_speed = seg["base_flow_speed"] * self.congestion_factor
        speed = max(5.0, base_speed + random.gauss(0, SPEED_NOISE_KPH))
        speed = min(speed, seg["speed_limit"])

        lat, lon = self._interpolate_position()

        # Move vehicle along segment
        self.progress += speed * PUBLISH_INTERVAL / 3600 / max(0.1, self._segment_length_km())
        self.progress = min(self.progress, 1.0)

        if self.progress >= 1.0:
            # Move to a new segment
            self.segment = random.choice(ROAD_SEGMENTS)
            self.progress = 0.0
            # Occasionally refresh congestion factor
            self.congestion_factor = random.uniform(0.3, 1.0)

        return GPSEvent(
            event_id=str(uuid.uuid4()),
            vehicle_id=self.vehicle_id,
            latitude=lat,
            longitude=lon,
            speed_kph=round(speed, 1),
            heading_degrees=self._heading(),
            road_segment_id=seg["id"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def _segment_length_km(self) -> float:
        seg = self.segment
        dlat = (seg["to_lat"] - seg["from_lat"]) * 111.0
        dlon = (seg["to_lon"] - seg["from_lon"]) * 111.0 * math.cos(math.radians(seg["from_lat"]))
        return max(0.01, math.hypot(dlat, dlon))


def make_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
        retries=5,
        retry_backoff_ms=500,
        linger_ms=100,
        batch_size=32_768,
    )


def on_send_error(exc: Exception) -> None:
    log.error("Failed to send GPS event: %s", exc)


def main() -> None:
    log.info("Starting GPS producer — %d vehicles, topic=%s", NUM_VEHICLES, GPS_TOPIC)
    vehicles = [VehicleSimulator(f"VEH-{i+1:04d}") for i in range(NUM_VEHICLES)]

    producer = make_producer()
    sent = 0
    try:
        while True:
            batch_start = time.time()
            for v in vehicles:
                event = v.next_event()
                producer.send(
                    topic=GPS_TOPIC,
                    key=event.vehicle_id,
                    value=asdict(event),
                ).add_errback(on_send_error)
                sent += 1

            producer.flush()
            elapsed = time.time() - batch_start
            sleep_time = max(0.0, PUBLISH_INTERVAL - elapsed)
            log.info("Published %d GPS events (total=%d). Next batch in %.1fs", NUM_VEHICLES, sent, sleep_time)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("GPS producer stopping…")
    finally:
        producer.close()
        log.info("GPS producer closed. Total events sent: %d", sent)


if __name__ == "__main__":
    main()
