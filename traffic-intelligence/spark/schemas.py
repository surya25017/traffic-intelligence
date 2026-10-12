"""
Pyspark schemas for GPS events and sensor events consumed from Kafka.
Centralised here so streaming_job.py and congestion_processor.py share the same definitions.
"""
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, IntegerType, LongType, TimestampType,
)

# ── GPS event schema (matches GPSEvent dataclass in gps_producer.py) ──────────
GPS_SCHEMA = StructType([
    StructField("event_id",        StringType(),  nullable=True),
    StructField("vehicle_id",      StringType(),  nullable=False),
    StructField("latitude",        DoubleType(),  nullable=False),
    StructField("longitude",       DoubleType(),  nullable=False),
    StructField("speed_kph",       DoubleType(),  nullable=False),
    StructField("heading_degrees", DoubleType(),  nullable=True),
    StructField("road_segment_id", StringType(),  nullable=False),
    StructField("timestamp",       StringType(),  nullable=False),
    StructField("event_type",      StringType(),  nullable=True),
    StructField("source",          StringType(),  nullable=True),
])

# ── Sensor event schema (matches SensorEvent dataclass in sensor_producer.py) ─
SENSOR_SCHEMA = StructType([
    StructField("event_id",             StringType(),  nullable=True),
    StructField("sensor_id",            StringType(),  nullable=False),
    StructField("segment_id",           StringType(),  nullable=False),
    StructField("vehicle_count",        IntegerType(), nullable=False),
    StructField("avg_speed_kph",        DoubleType(),  nullable=False),
    StructField("density_veh_per_km",   DoubleType(),  nullable=True),
    StructField("occupancy_pct",        DoubleType(),  nullable=True),
    StructField("flow_vph",             IntegerType(), nullable=True),
    StructField("timestamp",            StringType(),  nullable=False),
    StructField("event_type",           StringType(),  nullable=True),
    StructField("source",               StringType(),  nullable=True),
])

# ── Processed congestion result schema ────────────────────────────────────────
CONGESTION_SCHEMA = StructType([
    StructField("segment_id",        StringType(),  nullable=False),
    StructField("window_start",      StringType(),  nullable=False),
    StructField("window_end",        StringType(),  nullable=False),
    StructField("avg_speed_kph",     DoubleType(),  nullable=True),
    StructField("vehicle_count",     IntegerType(), nullable=True),
    StructField("density",           DoubleType(),  nullable=True),
    StructField("congestion_score",  DoubleType(),  nullable=True),
    StructField("congestion_level",  StringType(),  nullable=True),
    StructField("computed_at",       StringType(),  nullable=False),
])
