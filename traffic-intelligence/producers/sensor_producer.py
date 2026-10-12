"""
Traffic Sensor Producer — simulates roadside sensor readings and publishes to 'sensor-events'.

Sensors measure aggregate traffic flow on each road segment.
Data is SIMULATED — not from real sensors.
"""
import os
import json
import time
import random
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from kafka import KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [SENSOR-PRODUCER] %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP        = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
SENSOR_TOPIC           = os.getenv("SENSOR_TOPIC", "sensor-events")
SENSOR_PUBLISH_INTERVAL = float(os.getenv("SENSOR_PUBLISH_INTERVAL_S", "5.0"))

# Time-of-day multiplier presets (hour → congestion factor 0–1)
_HOUR_CONGESTION = {
    0: 0.05,  1: 0.05,  2: 0.05,  3: 0.05,  4: 0.08,
    5: 0.15,  6: 0.40,  7: 0.75,  8: 0.95,  9: 0.80,
    10: 0.60, 11: 0.55, 12: 0.65, 13: 0.60, 14: 0.55,
    15: 0.65, 16: 0.80, 17: 0.95, 18: 0.90, 19: 0.70,
    20: 0.50, 21: 0.35, 22: 0.20, 23: 0.10,
}

SENSORS = [
    {"sensor_id": "SEN-001", "segment_id": "SEG-AB", "capacity_vph": 2400, "free_flow_speed": 60},
    {"sensor_id": "SEN-002", "segment_id": "SEG-AC", "capacity_vph": 2400, "free_flow_speed": 60},
    {"sensor_id": "SEN-003", "segment_id": "SEG-AD", "capacity_vph": 1200, "free_flow_speed": 50},
    {"sensor_id": "SEN-004", "segment_id": "SEG-AE", "capacity_vph": 1200, "free_flow_speed": 50},
    {"sensor_id": "SEN-005", "segment_id": "SEG-BF", "capacity_vph": 2400, "free_flow_speed": 60},
    {"sensor_id": "SEN-006", "segment_id": "SEG-CF", "capacity_vph": 3600, "free_flow_speed": 70},
    {"sensor_id": "SEN-007", "segment_id": "SEG-CG", "capacity_vph": 2400, "free_flow_speed": 60},
    {"sensor_id": "SEN-008", "segment_id": "SEG-DG", "capacity_vph": 1200, "free_flow_speed": 50},
    {"sensor_id": "SEN-009", "segment_id": "SEG-DH", "capacity_vph": 1200, "free_flow_speed": 50},
    {"sensor_id": "SEN-010", "segment_id": "SEG-EH", "capacity_vph": 1200, "free_flow_speed": 50},
    {"sensor_id": "SEN-011", "segment_id": "SEG-EI", "capacity_vph": 2400, "free_flow_speed": 60},
    {"sensor_id": "SEN-012", "segment_id": "SEG-NO", "capacity_vph": 5400, "free_flow_speed": 80},
    {"sensor_id": "SEN-013", "segment_id": "SEG-OB", "capacity_vph": 2400, "free_flow_speed": 60},
]


@dataclass
class SensorEvent:
    event_id:              str
    sensor_id:             str
    segment_id:            str
    vehicle_count:         int
    avg_speed_kph:         float
    density_veh_per_km:    float
    occupancy_pct:         float
    flow_vph:              int
    timestamp:             str
    event_type:            str = "sensor_reading"
    source:                str = "simulated"


def _current_congestion_factor() -> float:
    """Returns a 0–1 congestion factor based on the current hour of day."""
    hour = datetime.now().hour
    base = _HOUR_CONGESTION.get(hour, 0.5)
    return min(1.0, max(0.0, base + random.gauss(0, 0.05)))


def generate_sensor_event(sensor: dict, congestion: float) -> SensorEvent:
    """
    Produce a realistic sensor reading.

    Greenshields model approximation:
        speed = free_flow * (1 - density/jam_density)
    """
    cap  = sensor["capacity_vph"]
    ff   = sensor["free_flow_speed"]

    # How loaded is the road? congestion=1 → near-jam
    load_ratio = congestion * random.uniform(0.85, 1.15)
    load_ratio = min(0.99, max(0.0, load_ratio))

    # Speed degrades as load rises (Greenshields model)
    speed = ff * (1.0 - load_ratio)
    speed = max(5.0, speed + random.gauss(0, 3))

    flow     = int(cap * load_ratio * random.uniform(0.9, 1.1))
    density  = round(flow / max(speed, 1), 2)         # vehicles per km
    occupancy = round(load_ratio * 100, 1)             # % of time loop is occupied
    count    = max(1, int(flow * (SENSOR_PUBLISH_INTERVAL / 3600)))

    return SensorEvent(
        event_id=str(uuid.uuid4()),
        sensor_id=sensor["sensor_id"],
        segment_id=sensor["segment_id"],
        vehicle_count=count,
        avg_speed_kph=round(speed, 1),
        density_veh_per_km=density,
        occupancy_pct=occupancy,
        flow_vph=flow,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def make_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
        retries=5,
        retry_backoff_ms=500,
    )


def on_send_error(exc: Exception) -> None:
    log.error("Failed to send sensor event: %s", exc)


def main() -> None:
    log.info("Starting sensor producer — %d sensors, topic=%s", len(SENSORS), SENSOR_TOPIC)
    producer = make_producer()
    sent = 0
    try:
        while True:
            congestion = _current_congestion_factor()
            for sensor in SENSORS:
                event = generate_sensor_event(sensor, congestion)
                producer.send(
                    topic=SENSOR_TOPIC,
                    key=event.segment_id,
                    value=asdict(event),
                ).add_errback(on_send_error)
                sent += 1
            producer.flush()
            log.info("Published %d sensor events (total=%d, congestion_factor=%.2f)",
                     len(SENSORS), sent, congestion)
            time.sleep(SENSOR_PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        log.info("Sensor producer stopping…")
    finally:
        producer.close()
        log.info("Sensor producer closed. Total events: %d", sent)


if __name__ == "__main__":
    main()
