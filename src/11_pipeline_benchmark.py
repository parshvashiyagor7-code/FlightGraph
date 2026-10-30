
from pathlib import Path
import json
import logging
import os
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
PROCESSED = ROOT / "data" / "processed"

REPORTS.mkdir(parents=True, exist_ok=True)

# Configure Windows environment for Spark.
os.environ.setdefault("HADOOP_HOME", r"C:\hadoop-3.5.0")
os.environ["PATH"] = (
    os.environ["HADOOP_HOME"] + r"\bin;" + os.environ.get("PATH", "")
)
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession


LOG_PATH = REPORTS / "day4_pipeline_benchmark.log"
JSON_PATH = REPORTS / "day4_benchmark.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)

log = logging.getLogger("FlightGraph")


def parquet_info(folder):
    files = list(folder.rglob("*.parquet"))
    total_bytes = sum(f.stat().st_size for f in files)
    return len(files), total_bytes


def main():
    audit_path = REPORTS / "etl_audit.json"
    validation_path = REPORTS / "data_quality_validation.json"

    if not audit_path.exists() or not validation_path.exists():
        raise FileNotFoundError(
            "Required ETL audit or data-quality validation report is missing."
        )

    with open(audit_path, encoding="utf-8") as f:
        audit = json.load(f)

    with open(validation_path, encoding="utf-8") as f:
        validation = json.load(f)

    audit_by_split = {
        item["split"]: item for item in audit["splits"]
    }
    validation_by_split = {
        item["split"]: item for item in validation["checks"]
    }

    spark = (
        SparkSession.builder
        .appName("FlightGraph-Day4-Benchmark")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    report = {
        "project": "FlightGraph",
        "benchmark_type": "Processed Parquet full-count scan",
        "spark_master": "local[2]",
        "splits": [],
    }

    try:
        for split in ["train", "val", "test"]:
            folder = PROCESSED / split
            log.info("Starting benchmark for %s", split)

            if not folder.exists():
                raise FileNotFoundError(
                    f"Processed dataset missing: {folder}"
                )

            file_count, total_bytes = parquet_info(folder)

            if file_count == 0:
                raise RuntimeError(
                    f"No Parquet files found in {folder}"
                )

            read_start = time.perf_counter()
            df = spark.read.parquet(str(folder))
            column_count = len(df.columns)
            read_seconds = time.perf_counter() - read_start

            scan_start = time.perf_counter()
            row_count = df.count()
            scan_seconds = time.perf_counter() - scan_start

            expected = int(audit_by_split[split]["accepted_rows"])
            validation_item = validation_by_split[split]

            count_match = row_count == expected
            validation_pass = validation_item["status"] == "PASS"

            result = {
                "split": split,
                "status": (
                    "PASS"
                    if count_match and validation_pass
                    else "FAIL"
                ),
                "rows": row_count,
                "audit_accepted_rows": expected,
                "columns": column_count,
                "parquet_file_count": file_count,
                "parquet_size_mb": round(total_bytes / (1024 ** 2), 2),
                "read_setup_seconds": round(read_seconds, 3),
                "full_count_scan_seconds": round(scan_seconds, 3),
                "scan_records_per_second": round(
                    row_count / scan_seconds, 2
                ) if scan_seconds > 0 else None,
                "audit_count_match": count_match,
                "previous_validation_pass": validation_pass,
            }

            report["splits"].append(result)
            log.info(
                "%s | rows=%s | files=%s | size_mb=%.2f | scan_seconds=%.2f | status=%s",
                split,
                f"{row_count:,}",
                file_count,
                result["parquet_size_mb"],
                scan_seconds,
                result["status"],
            )

        report["overall_status"] = (
            "PASS"
            if all(r["status"] == "PASS" for r in report["splits"])
            else "FAIL"
        )

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        log.info("Overall status: %s", report["overall_status"])
        log.info("JSON report saved to %s", JSON_PATH)
        log.info("Log file saved to %s", LOG_PATH)

    except Exception:
        log.exception("Benchmark failed")
        raise

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
