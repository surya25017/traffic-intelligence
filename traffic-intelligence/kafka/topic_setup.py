"""
Kafka topic setup script.
Run this once to create all required topics before starting producers or Spark.
"""
import os
import time
import logging
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

TOPICS = [
    NewTopic(name="gps-events",         num_partitions=4, replication_factor=1),
    NewTopic(name="sensor-events",      num_partitions=4, replication_factor=1),
    NewTopic(name="congestion-results", num_partitions=4, replication_factor=1),
    NewTopic(name="route-requests",     num_partitions=2, replication_factor=1),
]


def wait_for_kafka(retries: int = 15, delay: int = 5) -> KafkaAdminClient:
    """Retry until Kafka is ready."""
    for attempt in range(1, retries + 1):
        try:
            client = KafkaAdminClient(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                client_id="topic-setup",
                request_timeout_ms=10_000,
            )
            log.info("Connected to Kafka at %s", KAFKA_BOOTSTRAP)
            return client
        except NoBrokersAvailable:
            log.warning("Kafka not ready (attempt %d/%d). Retrying in %ds …", attempt, retries, delay)
            time.sleep(delay)
    raise RuntimeError("Could not connect to Kafka after %d attempts." % retries)


def create_topics(admin: KafkaAdminClient) -> None:
    for topic in TOPICS:
        try:
            admin.create_topics([topic])
            log.info("Created topic: %s (partitions=%d)", topic.name, topic.num_partitions)
        except TopicAlreadyExistsError:
            log.info("Topic already exists: %s", topic.name)


if __name__ == "__main__":
    admin = wait_for_kafka()
    create_topics(admin)
    admin.close()
    log.info("Topic setup complete.")
