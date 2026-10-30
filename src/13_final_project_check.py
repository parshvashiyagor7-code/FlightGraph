
from pathlib import Path
import ast
import csv
import json

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
PROCESSED = ROOT / "data" / "processed"

results = []


def check(name, passed, details=""):
    results.append({
        "check": name,
        "status": "PASS" if passed else "FAIL",
        "details": details,
    })
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" - {details}" if details else ""))


def read_json(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    print("\nFLIGHTGRAPH FINAL PROJECT CHECK")
    print("=" * 48)

    # Required reports and dashboard
    required_files = [
        REPORTS / "etl_audit.json",
        REPORTS / "data_quality_validation.json",
        REPORTS / "day4_benchmark.json",
        REPORTS / "eda_summary.csv",
        REPORTS / "monthly_delay.csv",
        REPORTS / "airline_delay.csv",
        ROOT / "dashboard" / "app.py",
    ]

    for path in required_files:
        check(
            f"File exists: {path.relative_to(ROOT)}",
            path.is_file(),
        )

    # ETL audit
    audit_path = REPORTS / "etl_audit.json"
    if audit_path.is_file():
        try:
            audit = read_json(audit_path)
            splits = {x["split"]: x for x in audit["splits"]}
            expected = ["train", "val", "test"]

            check(
                "ETL audit contains all splits",
                all(s in splits for s in expected),
            )

            if all(s in splits for s in expected):
                counts_ok = all(
                    int(splits[s]["input_rows"])
                    == int(splits[s]["accepted_rows"])
                    + int(splits[s]["rejected_rows"])
                    for s in expected
                )
                check("ETL count arithmetic", counts_ok)

                total = sum(
                    int(splits[s]["input_rows"]) for s in expected
                )
                check(
                    "Total input record count",
                    total == 44_858_151,
                    f"{total:,} records",
                )
        except Exception as exc:
            check("ETL audit readable", False, str(exc))

    # Validation report
    validation_path = REPORTS / "data_quality_validation.json"
    if validation_path.is_file():
        try:
            report = read_json(validation_path)
            check(
                "Data quality overall status",
                report.get("overall_status") == "PASS",
            )

            status_by_split = {
                x["split"]: x["status"]
                for x in report.get("checks", [])
            }
            check(
                "Train/validation/test checks",
                all(
                    status_by_split.get(s) == "PASS"
                    for s in ["train", "val", "test"]
                ),
            )
        except Exception as exc:
            check("Validation report readable", False, str(exc))

    # Benchmark report
    benchmark_path = REPORTS / "day4_benchmark.json"
    if benchmark_path.is_file():
        try:
            benchmark = read_json(benchmark_path)
            check(
                "Benchmark overall status",
                benchmark.get("overall_status") == "PASS",
            )
        except Exception as exc:
            check("Benchmark report readable", False, str(exc))

    # Processed Parquet files
    for split in ["train", "val", "test"]:
        folder = PROCESSED / split
        files = list(folder.rglob("*.parquet")) if folder.is_dir() else []

        check(
            f"Processed Parquet: {split}",
            len(files) > 0,
            f"{len(files)} files found",
        )

    # EDA CSV files
    for filename in [
        "eda_summary.csv",
        "monthly_delay.csv",
        "airline_delay.csv",
    ]:
        path = REPORTS / filename
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                first_row = next(reader, None)

            check(
                f"CSV readable: {filename}",
                bool(headers) and first_row is not None,
            )
        except Exception as exc:
            check(f"CSV readable: {filename}", False, str(exc))

    # Dashboard syntax check; does not import Streamlit/Pandas.
    dashboard = ROOT / "dashboard" / "app.py"
    if dashboard.is_file():
        try:
            ast.parse(dashboard.read_text(encoding="utf-8"))
            check("Dashboard Python syntax", True)
        except Exception as exc:
            check("Dashboard Python syntax", False, str(exc))

    passed = sum(x["status"] == "PASS" for x in results)
    failed = sum(x["status"] == "FAIL" for x in results)

    final_report = {
        "project": "FlightGraph",
        "passed_checks": passed,
        "failed_checks": failed,
        "overall_status": "PASS" if failed == 0 else "FAIL",
        "results": results,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / "final_project_check.json"
    output.write_text(json.dumps(final_report, indent=2), encoding="utf-8")

    print("\n" + "=" * 48)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Overall: {final_report['overall_status']}")
    print(f"Report saved: {output}")


if __name__ == "__main__":
    main()
