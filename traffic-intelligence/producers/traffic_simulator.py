"""
Traffic Simulator — convenience wrapper that runs both GPS and Sensor producers
in separate threads so you can start the entire simulation with one command.

Usage:
    python producers/traffic_simulator.py
"""
import logging
import threading
import sys
import os

# Allow imports from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from producers.gps_producer    import main as run_gps
from producers.sensor_producer import main as run_sensor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [SIMULATOR] %(message)s",
)
log = logging.getLogger(__name__)


def start_thread(target, name: str) -> threading.Thread:
    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()
    log.info("Started thread: %s (tid=%d)", name, t.ident)
    return t


def main() -> None:
    log.info("=" * 60)
    log.info("  Traffic Intelligence — Data Simulator")
    log.info("  NOTE: All data is SIMULATED for demonstration.")
    log.info("=" * 60)

    gps_thread    = start_thread(run_gps,    "GPSProducer")
    sensor_thread = start_thread(run_sensor, "SensorProducer")

    try:
        gps_thread.join()
        sensor_thread.join()
    except KeyboardInterrupt:
        log.info("Simulator stopped by user.")


if __name__ == "__main__":
    main()
