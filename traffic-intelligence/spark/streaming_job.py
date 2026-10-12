"""
Spark Structured Streaming Job
================================
Reads GPS and sensor events from Kafka, aggregates them per road segment over
sliding time windows, computes congestion scores, writes results to:
  1. A Kafka topic 'congestion-results' (for downstream consumers).
  2. A local SQLite database (for the FastAPI backend to query).

Run inside the Spark container:
    spark-submit \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
        spark/streaming_job.py

Environment variables (all have defaults):
    KAFKA_BOOTSTRAP_SERVERS  — e.g. kafka:9092
    GPS_TOPIC                — default: gps-events
    SENSOR_TOPIC             — default: sensor-events
    CONGESTION_TOPIC         — default: congestion-results
    CHECKPOINT_DIR           — default: /app/checkpoints
    WINDOW_DURATION_S        — default: 60  (aggregation window in seconds)
    SLIDE_DURATION_S         — default: 30  (slide interval in seconds)
    WATERMARK_DELAY_S        — default: 30  (late-event tolerance in seconds)
    DB_PATH                  — path to SQLite file
"""
import os
import json
import logging
import sqlite3
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType

# Import shared schemas and congestion logic
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark.schemas import GPS_SCHEMA, SENSOR_SCHEMA
from spark.congestion_processor import (
    SegmentInput, calculate_congestion_score, classify_congestion,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [SPARK-JOB] %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP    = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
GPS_TOPIC          = os.getenv("GPS_TOPIC",          "gps-events")
SENSOR_TOPIC       = os.getenv("SENSOR_TOPIC",       "sensor-events")
CONGESTION_TOPIC   = os.getenv("CONGESTION_TOPIC",   "congestion-results")
CHECKPOINT_DIR     = os.getenv("CHECKPOINT_DIR",     "/app/checkpoints")
WINDOW_DURATION_S  = int(os.getenv("WINDOW_DURATION_S",  "60"))
SLIDE_DURATION_S   = int(os.getenv("SLIDE_DURATION_S",   "30"))
WATERMARK_DELAY_S  = int(os.getenv("WATERMARK_DELAY_S",  "30"))
DB_PATH            = os.getenv("DB_PATH", "/app/data/traffic.db")

SEGMENT_CAPACITIES: dict[str, float] = {
    "SEG-AB": 2400, "SEG-AC": 2400, "SEG-AD": 1200, "SEG-AE": 1200,
    "SEG-BF": 2400, "SEG-CF": 3600, "SEG-CG": 2400, "SEG-DG": 1200,
    "SEG-DH": 1200, "SEG-EH": 1200, "SEG-EI": 2400, "SEG-NO": 5400,
    "SEG-OB": 2400, "SEG-NR": 3600, "SEG-PG": 2400, "SEG-QI": 2400,
    "SEG-RE": 1200,
}
SPEED_LIMITS: dict[str, float] = {
    "SEG-AB": 60, "SEG-AC": 60, "SEG-AD": 50, "SEG-AE": 50,
    "SEG-BF": 60, "SEG-CF": 70, "SEG-CG": 60, "SEG-DG": 50,
    "SEG-DH": 50, "SEG-EH": 50, "SEG-EI": 60, "SEG-NO": 80,
    "SEG-OB": 60, "SEG-NR": 70, "SEG-PG": 60, "SEG-QI": 60,
    "SEG-RE": 50,
}

# ── SQLite initialisation ─────────────────────────────────────────────────────

def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS congestion_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id      TEXT NOT NULL,
            window_start    TEXT NOT NULL,
            window_end      TEXT NOT NULL,
            avg_speed_kph   REAL,
            vehicle_count   INTEGER,
            density         REAL,
            congestion_score REAL,
            congestion_level TEXT,
            computed_at     TEXT NOT NULL,
            UNIQUE(segment_id, window_start)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seg_time ON congestion_history(segment_id, window_start)")
    conn.commit()
    conn.close()
    log.info("SQLite database ready at %s", db_path)


# ── UDF: compute congestion score ─────────────────────────────────────────────

def _score_udf_impl(segment_id, avg_speed, vehicle_count, density):
    speed_limit = SPEED_LIMITS.get(segment_id, 50.0)
    capacity    = SEGMENT_CAPACITIES.get(segment_id)
    inp = SegmentInput(
        segment_id=segment_id or "UNKNOWN",
        avg_speed_kph=float(avg_speed) if avg_speed is not None else None,
        speed_limit_kph=speed_limit,
        vehicle_count=int(vehicle_count) if vehicle_count is not None else None,
        road_capacity_vph=capacity,
        density_veh_per_km=float(density) if density is not None else None,
    )
    result = calculate_congestion_score(inp)
    return result.congestion_score


def _level_udf_impl(score):
    if score is None:
        return "UNKNOWN"
    return classify_congestion(float(score))


# ── Kafka sink: write congestion results back to Kafka ────────────────────────

def write_to_kafka_and_db(batch_df, batch_id: int) -> None:
    """
    foreachBatch sink:
      1. Writes congestion records to the Kafka topic 'congestion-results'.
      2. Upserts records into SQLite for the FastAPI backend.
    """
    if batch_df.rdd.isEmpty():
        return

    rows = batch_df.collect()
    computed_at = datetime.now(timezone.utc).isoformat()

    # ── 1. Build Kafka-ready records ─────────────────────────────────────────
    kafka_rows = []
    db_rows    = []

    for row in rows:
        payload = {
            "segment_id":       row["segment_id"],
            "window_start":     str(row["window_start"]),
            "window_end":       str(row["window_end"]),
            "avg_speed_kph":    round(float(row["avg_speed_kph"]), 2) if row["avg_speed_kph"] else None,
            "vehicle_count":    int(row["vehicle_count"]) if row["vehicle_count"] else 0,
            "density":          round(float(row["density"]), 2) if row["density"] else None,
            "congestion_score": round(float(row["congestion_score"]), 2) if row["congestion_score"] else 0.0,
            "congestion_level": row["congestion_level"] or "UNKNOWN",
            "computed_at":      computed_at,
        }
        kafka_rows.append({
            "key":   row["segment_id"],
            "value": json.dumps(payload),
        })
        db_rows.append((
            payload["segment_id"],
            payload["window_start"],
            payload["window_end"],
            payload["avg_speed_kph"],
            payload["vehicle_count"],
            payload["density"],
            payload["congestion_score"],
            payload["congestion_level"],
            computed_at,
        ))
        log.info("Batch %d | %s → score=%.1f level=%s",
                 batch_id, payload["segment_id"],
                 payload["congestion_score"], payload["congestion_level"])

    # ── 2. Write to Kafka ─────────────────────────────────────────────────────
    spark = SparkSession.getActiveSession()
    if spark and kafka_rows:
        try:
            kafka_df = spark.createDataFrame(kafka_rows)
            (kafka_df
             .write
             .format("kafka")
             .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
             .option("topic", CONGESTION_TOPIC)
             .save())
        except Exception as exc:
            log.error("Kafka write failed: %s", exc)

    # ── 3. Upsert into SQLite ─────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.executemany("""
            INSERT OR REPLACE INTO congestion_history
                (segment_id, window_start, window_end, avg_speed_kph,
                 vehicle_count, density, congestion_score, congestion_level, computed_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, db_rows)
        conn.commit()
        conn.close()
    except Exception as exc:
        log.error("SQLite write failed: %s", exc)


# ── Main streaming job ────────────────────────────────────────────────────────

def build_spark_session() -> SparkSession:
    return (SparkSession.builder
            .appName("TrafficIntelligence-StreamingJob")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.streaming.stopGracefullyOnShutdown", "true")
            .getOrCreate())


def main() -> None:
    init_db(DB_PATH)

    spark = build_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    score_udf = F.udf(_score_udf_impl, DoubleType())
    level_udf = F.udf(_level_udf_impl, StringType())

    window_dur = f"{WINDOW_DURATION_S} seconds"
    slide_dur  = f"{SLIDE_DURATION_S} seconds"
    watermark  = f"{WATERMARK_DELAY_S} seconds"

    # ── Read GPS events ───────────────────────────────────────────────────────
    gps_raw = (spark.readStream
               .format("kafka")
               .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
               .option("subscribe", GPS_TOPIC)
               .option("startingOffsets", "latest")
               .option("failOnDataLoss", "false")
               .load())

    gps_parsed = (gps_raw
                  .select(F.from_json(F.col("value").cast("string"), GPS_SCHEMA).alias("data"))
                  .select("data.*")
                  .filter(F.col("vehicle_id").isNotNull())
                  .filter(F.col("road_segment_id").isNotNull())
                  .filter(F.col("speed_kph") >= 0)
                  .withColumn("event_time", F.to_timestamp("timestamp"))
                  .withWatermark("event_time", watermark))

    # ── Read Sensor events ────────────────────────────────────────────────────
    sensor_raw = (spark.readStream
                  .format("kafka")
                  .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
                  .option("subscribe", SENSOR_TOPIC)
                  .option("startingOffsets", "latest")
                  .option("failOnDataLoss", "false")
                  .load())

    sensor_parsed = (sensor_raw
                     .select(F.from_json(F.col("value").cast("string"), SENSOR_SCHEMA).alias("data"))
                     .select("data.*")
                     .filter(F.col("segment_id").isNotNull())
                     .filter(F.col("avg_speed_kph") >= 0)
                     .withColumn("event_time", F.to_timestamp("timestamp"))
                     .withWatermark("event_time", watermark))

    # ── Aggregate GPS by segment over sliding window ──────────────────────────
    gps_agg = (gps_parsed
               .groupBy(F.window("event_time", window_dur, slide_dur),
                        F.col("road_segment_id").alias("segment_id"))
               .agg(F.avg("speed_kph").alias("gps_avg_speed"),
                    F.count("vehicle_id").alias("gps_vehicle_count")))

    # ── Aggregate Sensor data by segment ─────────────────────────────────────
    sensor_agg = (sensor_parsed
                  .groupBy(F.window("event_time", window_dur, slide_dur),
                           F.col("segment_id"))
                  .agg(F.avg("avg_speed_kph").alias("sensor_avg_speed"),
                       F.avg("density_veh_per_km").alias("avg_density"),
                       F.avg("vehicle_count").alias("sensor_vehicle_count")))

    # ── Join GPS + Sensor (outer join to keep segments with only one source) ──
    joined = (gps_agg.alias("g")
              .join(sensor_agg.alias("s"),
                    (F.col("g.segment_id") == F.col("s.segment_id")) &
                    (F.col("g.window") == F.col("s.window")),
                    how="full_outer")
              .select(
                  F.coalesce(F.col("g.segment_id"), F.col("s.segment_id")).alias("segment_id"),
                  F.coalesce(F.col("g.window"),     F.col("s.window")).alias("window"),
                  F.coalesce(F.col("gps_avg_speed"), F.col("sensor_avg_speed")).alias("avg_speed_kph"),
                  F.coalesce(F.col("gps_vehicle_count").cast("double"),
                             F.col("sensor_vehicle_count")).alias("vehicle_count"),
                  F.col("avg_density").alias("density"),
              ))

    # ── Compute congestion score and level ────────────────────────────────────
    with_score = (joined
                  .withColumn("congestion_score",
                              score_udf("segment_id", "avg_speed_kph",
                                        "vehicle_count", "density"))
                  .withColumn("congestion_level",
                              level_udf("congestion_score"))
                  .select(
                      "segment_id",
                      F.col("window.start").alias("window_start"),
                      F.col("window.end").alias("window_end"),
                      "avg_speed_kph",
                      F.col("vehicle_count").cast("int"),
                      "density",
                      "congestion_score",
                      "congestion_level",
                  ))

    # ── Write results via foreachBatch ────────────────────────────────────────
    query = (with_score.writeStream
             .outputMode("update")
             .option("checkpointLocation", os.path.join(CHECKPOINT_DIR, "congestion"))
             .foreachBatch(write_to_kafka_and_db)
             .trigger(processingTime=f"{SLIDE_DURATION_S} seconds")
             .start())

    log.info("Streaming job started. Window=%s, Slide=%s, Watermark=%s",
             window_dur, slide_dur, watermark)
    query.awaitTermination()


if __name__ == "__main__":
    main()
