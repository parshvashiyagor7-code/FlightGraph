
from pathlib import Path
from datetime import datetime
import json

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
REPORTS_DIR = ROOT / "reports"

SPLITS = ["train", "val", "test"]

REQUIRED = [
    "date",
    "Year",
    "Month",
    "Origin",
    "Dest",
    "Reporting_Airline",
    "ArrDel15",
]


def main():
    audit_path = REPORTS_DIR / "etl_audit.json"

    if not audit_path.exists():
        raise FileNotFoundError(f"Audit report not found: {audit_path}")

    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    audit_by_split = {
        item["split"]: item for item in audit["splits"]
    }

    spark = (
        SparkSession.builder
        .appName("FlightGraph-Data-Quality-Validation")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    report = {
        "validation_time": datetime.now().isoformat(timespec="seconds"),
        "checks": [],
        "overall_status": "PASS",
    }

    try:
        for split in SPLITS:
            print(f"\nValidating {split}...", flush=True)

            path = PROCESSED_DIR / split

            if not path.exists():
                raise FileNotFoundError(
                    f"Processed split not found: {path}"
                )

            df = spark.read.parquet(str(path))

            missing = [c for c in REQUIRED if c not in df.columns]
            if missing:
                raise ValueError(f"{split}: missing columns {missing}")

            date = F.col("date")
            year = F.col("Year").cast("int")
            month = F.col("Month").cast("int")
            label = F.col("ArrDel15").cast("int")

            checks = {
                "null_dates": date.isNull(),
                "missing_origin": (
                    F.col("Origin").isNull()
                    | (F.trim(F.col("Origin")) == "")
                ),
                "missing_destination": (
                    F.col("Dest").isNull()
                    | (F.trim(F.col("Dest")) == "")
                ),
                "missing_airline": (
                    F.col("Reporting_Airline").isNull()
                    | (F.trim(F.col("Reporting_Airline")) == "")
                ),
                "invalid_arr_delay_label": (
                    label.isNull() | (~label.isin(0, 1))
                ),
                "invalid_year": (
                    year.isNull() | (year < 1900) | (year > 2100)
                ),
                "invalid_month": (
                    month.isNull() | (~month.between(1, 12))
                ),
                "date_year_mismatch": (
                    date.isNull()
                    | year.isNull()
                    | (F.year(date) != year)
                ),
                "date_month_mismatch": (
                    date.isNull()
                    | month.isNull()
                    | (F.month(date) != month)
                ),
            }

            expressions = [
                F.count("*").alias("row_count")
            ]

            for name, condition in checks.items():
                expressions.append(
                    F.sum(
                        F.when(condition, 1).otherwise(0)
                    ).alias(name)
                )

            result = df.agg(*expressions).first().asDict()
            audit_item = audit_by_split[split]

            actual_rows = int(result["row_count"])
            expected_rows = int(audit_item["accepted_rows"])

            check_results = {
                name: int(result[name] or 0)
                for name in checks
            }

            split_pass = (
                actual_rows == expected_rows
                and all(value == 0 for value in check_results.values())
            )

            split_result = {
                "split": split,
                "status": "PASS" if split_pass else "FAIL",
                "actual_rows": actual_rows,
                "audit_accepted_rows": expected_rows,
                "checks": check_results,
            }

            report["checks"].append(split_result)

            print(f"Rows: {actual_rows:,}")
            print(f"Audit count: {expected_rows:,}")
            print(f"Status: {split_result['status']}")

            for name, count in check_results.items():
                print(f"  {name}: {count:,}")

        if any(item["status"] == "FAIL" for item in report["checks"]):
            report["overall_status"] = "FAIL"

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = REPORTS_DIR / "data_quality_validation.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"\nOverall status: {report['overall_status']}")
        print(f"Report saved: {output_path}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
