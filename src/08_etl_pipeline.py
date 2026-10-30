
from pathlib import Path
from datetime import datetime
import json

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REJECTED_DIR = ROOT / "data" / "rejected"
REPORT_DIR = ROOT / "reports"

SPLITS = ["train", "val", "test"]

REQUIRED_COLUMNS = [
    "date",
    "Year",
    "Month",
    "Origin",
    "Dest",
    "Reporting_Airline",
    "ArrDel15",
]


def transform_and_validate(df):
    # Standardize categorical codes.
    for name in ["Origin", "Dest", "Reporting_Airline"]:
        df = df.withColumn(
            name,
            F.upper(F.trim(F.col(name).cast("string"))),
        )

    # Safely parse fields; malformed values become null.
    df = df.withColumn(
        "date",
        F.expr("try_cast(`date` AS DATE)"),
    )

    df = df.withColumn(
        "ArrDel15",
        F.expr("try_cast(`ArrDel15` AS INT)"),
    )

    checks = [
        (
            "invalid_date",
            F.col("date").isNull(),
        ),
        (
            "missing_origin",
            F.col("Origin").isNull() | (F.col("Origin") == ""),
        ),
        (
            "missing_destination",
            F.col("Dest").isNull() | (F.col("Dest") == ""),
        ),
        (
            "missing_airline",
            F.col("Reporting_Airline").isNull()
            | (F.col("Reporting_Airline") == ""),
        ),
        (
            "invalid_arr_delay_label",
            F.col("ArrDel15").isNull()
            | (~F.col("ArrDel15").isin(0, 1)),
        ),
        (
            "invalid_year",
            F.col("Year").isNull()
            | F.expr("try_cast(`Year` AS INT)").isNull(),
        ),
        (
            "invalid_month",
            F.col("Month").isNull()
            | (~F.expr("try_cast(`Month` AS INT)").between(1, 12)),
        ),
    ]

    reasons = [
        F.when(condition, F.lit(reason))
        for reason, condition in checks
    ]

    df = df.withColumn(
        "etl_reject_reason",
        F.concat_ws(";", *reasons),
    )

    df = df.withColumn(
        "_is_valid",
        F.length("etl_reject_reason") == 0,
    )

    return df


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-ETL")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")
    audit = {
        "pipeline": "FlightGraph ETL",
        "run_timestamp": datetime.now().isoformat(timespec="seconds"),
        "splits": [],
    }

    try:
        for split in SPLITS:
            source = RAW_DIR / f"{split}.parquet"

            print(f"\nProcessing {split}...", flush=True)

            if not source.exists():
                raise FileNotFoundError(f"Raw dataset not found: {source}")

            df = spark.read.parquet(str(source))

            missing = [
                name for name in REQUIRED_COLUMNS
                if name not in df.columns
            ]

            if missing:
                raise ValueError(
                    f"{split}: required columns missing: {missing}"
                )

            df = transform_and_validate(df)

            # Get accepted/rejected counts in one aggregation.
            count_rows = (
                df.groupBy("_is_valid")
                .count()
                .collect()
            )

            counts = {
                bool(row["_is_valid"]): int(row["count"])
                for row in count_rows
            }

            accepted_count = counts.get(True, 0)
            rejected_count = counts.get(False, 0)

            accepted_path = PROCESSED_DIR / split
            rejected_path = REJECTED_DIR / split

            accepted = (
                df.filter(F.col("_is_valid"))
                .drop("_is_valid", "etl_reject_reason")
            )

            rejected = df.filter(~F.col("_is_valid")).drop("_is_valid")

            # Raw files are never modified.
            accepted.write.mode("overwrite").option(
                "compression", "snappy"
            ).parquet(str(accepted_path))

            rejected.write.mode("overwrite").option(
                "compression", "snappy"
            ).parquet(str(rejected_path))

            split_audit = {
                "split": split,
                "input_rows": accepted_count + rejected_count,
                "accepted_rows": accepted_count,
                "rejected_rows": rejected_count,
                "processed_path": str(accepted_path),
                "rejected_path": str(rejected_path),
            }

            audit["splits"].append(split_audit)

            print(f"Input rows:    {accepted_count + rejected_count:,}")
            print(f"Accepted rows: {accepted_count:,}")
            print(f"Rejected rows: {rejected_count:,}")
            print("ETL split completed.", flush=True)

        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        audit_path = REPORT_DIR / "etl_audit.json"
        with open(audit_path, "w", encoding="utf-8") as file:
            json.dump(audit, file, indent=2)

        print(f"\nETL completed successfully.")
        print(f"Audit report: {audit_path}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
