
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"

FILES = ["train.parquet", "val.parquet", "test.parquet"]

# (minimum, maximum, minimum_is_strict)
RULES = {
    "Quarter": (1, 4, False),
    "Month": (1, 12, False),
    "DayofMonth": (1, 31, False),
    "DayOfWeek": (1, 7, False),
    "Distance": (0, None, True),
    "CRSElapsedTime": (0, None, True),
    "origin_humidity": (0, 100, False),
    "dest_humidity": (0, 100, False),
    "origin_wind_kts": (0, None, False),
    "dest_wind_kts": (0, None, False),
    "origin_gust_kts": (0, None, False),
    "dest_gust_kts": (0, None, False),
    "origin_visibility": (0, None, False),
    "dest_visibility": (0, None, False),
    "origin_precip_in": (0, None, False),
    "dest_precip_in": (0, None, False),
}


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-Invalid-Values")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    try:
        for filename in FILES:
            path = DATA_DIR / filename

            print(f"\n{'=' * 45}")
            print(f"DATASET: {filename}")

            if not path.exists():
                print("File not found:", path)
                continue

            df = spark.read.parquet(str(path))

            available = [
                name for name in RULES if name in df.columns
            ]

            # Inspect a 1% sample first; do not modify original data.
            sample = df.select(*available).sample(
                withReplacement=False,
                fraction=0.01,
                seed=42,
            )

            expressions = []

            for name in available:
                value = F.col(name).cast("double")
                lower, upper, strict_lower = RULES[name]

                bad = value.isNull() | F.isnan(value)

                if lower is not None:
                    if strict_lower:
                        bad = bad | (value <= lower)
                    else:
                        bad = bad | (value < lower)

                if upper is not None:
                    bad = bad | (value > upper)

                expressions.append(
                    F.sum(
                        F.when(bad, 1).otherwise(0)
                    ).alias(name)
                )

            if expressions:
                counts = sample.agg(*expressions).first().asDict()

                print("\nInvalid values in sampled records:")
                found = False

                for name, count in counts.items():
                    count = int(count or 0)
                    if count > 0:
                        print(f"{name}: {count:,}")
                        found = True

                if not found:
                    print("No invalid values detected in sampled columns.")

            print("Checked columns:", len(available))

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
