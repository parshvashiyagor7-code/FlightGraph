
from pathlib import Path
import csv

from pyspark.sql import SparkSession, functions as F

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "raw" / "train.parquet"
OUT = ROOT / "reports"
OUT.mkdir(parents=True, exist_ok=True)


def save_csv(path, rows):
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def calculate_stats(df, group_columns=None):
    label = F.col("ArrDel15").cast("double")
    valid = label.isin(0.0, 1.0)

    aggregations = [
        F.count("*").alias("flight_records"),
        F.sum(F.when(valid, 1).otherwise(0)).alias("valid_labels"),
        F.sum(F.when(label == 1.0, 1).otherwise(0))
        .alias("delayed_15min_or_more"),
    ]

    if group_columns:
        result = (
            df.groupBy(*group_columns)
            .agg(*aggregations)
            .orderBy(*group_columns)
            .collect()
        )
    else:
        result = [df.agg(*aggregations).first()]

    rows = []

    for item in result:
        row = item.asDict()
        valid_count = row["valid_labels"] or 0
        delayed_count = row["delayed_15min_or_more"] or 0

        row["delayed_15min_or_more_pct"] = (
            round(100 * delayed_count / valid_count, 2)
            if valid_count else None
        )

        rows.append(row)

    return rows


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-EDA")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    try:
        df = spark.read.parquet(str(DATA))

        required = ["Year", "Month", "Reporting_Airline", "ArrDel15"]
        missing = [c for c in required if c not in df.columns]

        if missing:
            print("Required columns not found:", missing)
            print("Available columns:", df.columns)
            return

        # Keep only the columns required for this EDA.
        df = df.select(*required)

        print("Calculating overall statistics...")
        overall = calculate_stats(df)
        save_csv(OUT / "eda_summary.csv", overall)

        print("Calculating monthly statistics...")
        monthly = calculate_stats(df, ["Year", "Month"])
        save_csv(OUT / "monthly_delay.csv", monthly)

        print("Calculating airline statistics...")
        airline = calculate_stats(df, ["Reporting_Airline"])
        save_csv(OUT / "airline_delay.csv", airline)

        print("\nEDA completed successfully.")
        print("Reports saved to:", OUT)

        print("\nOverall results:")
        for key, value in overall[0].items():
            print(f"{key}: {value}")

        print("\nAirlines with highest percentage of delayed flights:")
        ranked = sorted(
            airline,
            key=lambda row: row["delayed_15min_or_more_pct"]
            if row["delayed_15min_or_more_pct"] is not None else -1,
            reverse=True,
        )

        for row in ranked[:10]:
            print(
                row["Reporting_Airline"],
                "| flights:", row["flight_records"],
                "| delayed %:", row["delayed_15min_or_more_pct"],
            )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
