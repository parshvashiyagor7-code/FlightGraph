
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"

FILES = ["train.parquet", "val.parquet", "test.parquet"]

KEYS = [
    "FlightDate",
    "Reporting_Airline",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
]

SAMPLE_FRACTION = 0.005


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-Duplicate-Check")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    try:
        for filename in FILES:
            path = DATA_DIR / filename

            print(f"\n{'=' * 50}", flush=True)
            print(f"DATASET: {filename}", flush=True)

            if not path.exists():
                print(f"File not found: {path}")
                continue

            df = spark.read.parquet(str(path))

            missing_keys = [c for c in KEYS if c not in df.columns]
            if missing_keys:
                print("Missing key columns:", missing_keys)
                continue

            sample_df = df.select(*KEYS).sample(
                withReplacement=False,
                fraction=SAMPLE_FRACTION,
                seed=42,
            )

            duplicate_groups = (
                sample_df.groupBy(*KEYS)
                .count()
                .filter(F.col("count") > 1)
            )

            summary = duplicate_groups.agg(
                F.count("*").alias("duplicate_key_groups"),
                F.sum(F.col("count") - 1).alias("extra_records"),
            ).first()

            print(
                "Duplicate key groups in sample:",
                int(summary["duplicate_key_groups"] or 0),
            )
            print(
                "Extra records in those groups:",
                int(summary["extra_records"] or 0),
            )

            if summary["duplicate_key_groups"] > 0:
                print("\nExample groups to investigate:")
                duplicate_groups.orderBy(
                    F.desc("count")
                ).show(5, truncate=False)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
