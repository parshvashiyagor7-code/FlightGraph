from __future__ import annotations

from pathlib import Path
import shutil

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "processed" / "train"
REPORTS_PATH = ROOT / "reports"
OUTPUT_CSV = REPORTS_PATH / "route_delay.csv"
TEMP_OUTPUT = REPORTS_PATH / "_route_delay_csv_tmp"


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Processed training Parquet folder not found: {INPUT_PATH}. "
            "Run the ETL pipeline first."
        )

    REPORTS_PATH.mkdir(parents=True, exist_ok=True)
    if TEMP_OUTPUT.exists():
        shutil.rmtree(TEMP_OUTPUT)

    spark = (
        SparkSession.builder
        .appName("FlightGraph-Route-Analysis")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "16")
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    try:
        print(f"Reading processed training data from: {INPUT_PATH}")
        flights = spark.read.parquet(str(INPUT_PATH))
        required = {"Origin", "Dest", "ArrDel15"}
        missing = required.difference(flights.columns)
        if missing:
            raise ValueError(
                "Processed training data is missing required columns: "
                + ", ".join(sorted(missing))
            )

        valid = (
            flights.select("Origin", "Dest", "ArrDel15")
            .withColumn("Origin", F.upper(F.trim(F.col("Origin").cast("string"))))
            .withColumn("Dest", F.upper(F.trim(F.col("Dest").cast("string"))))
            .withColumn("ArrDel15", F.col("ArrDel15").cast("int"))
            .filter(F.col("Origin").isNotNull() & (F.col("Origin") != ""))
            .filter(F.col("Dest").isNotNull() & (F.col("Dest") != ""))
            .filter(F.col("ArrDel15").isin(0, 1))
        )

        route_summary = (
            valid.groupBy("Origin", "Dest")
            .agg(
                F.count(F.lit(1)).cast("long").alias("flight_records"),
                F.sum(
                    F.when(F.col("ArrDel15") == 1, F.lit(1)).otherwise(F.lit(0))
                ).cast("long").alias("delayed_15min_or_more"),
            )
            .withColumn(
                "delayed_15min_or_more_pct",
                F.round(
                    F.col("delayed_15min_or_more") / F.col("flight_records") * 100,
                    2,
                ),
            )
            .select(
                "Origin", "Dest", "flight_records",
                "delayed_15min_or_more", "delayed_15min_or_more_pct",
            )
        )

        print("Aggregating routes and writing compact CSV report...")
        (
            route_summary.coalesce(1)
            .write.mode("overwrite")
            .option("header", "true")
            .option("encoding", "UTF-8")
            .csv(str(TEMP_OUTPUT))
        )

        part_files = list(TEMP_OUTPUT.glob("part-*.csv"))
        if not part_files:
            raise RuntimeError("Spark did not produce a route analysis CSV part file.")

        if OUTPUT_CSV.exists():
            OUTPUT_CSV.unlink()
        shutil.move(str(part_files[0]), str(OUTPUT_CSV))
        shutil.rmtree(TEMP_OUTPUT, ignore_errors=True)
        print(f"PASS: Route analysis report created: {OUTPUT_CSV}")
        print("Open/refresh the Streamlit dashboard to view Flight Route Analysis.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
