
from pathlib import Path

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"
FILES = ["train.parquet", "val.parquet", "test.parquet"]

BATCH_SIZE = 8


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-Data-Quality")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.files.maxPartitionBytes", str(64 * 1024 * 1024))
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    try:
        for filename in FILES:
            path = DATA_DIR / filename

            print(f"\n{'=' * 50}", flush=True)
            print(f"DATASET: {filename}", flush=True)

            if not path.exists():
                print(f"File not found: {path}", flush=True)
                continue

            df = spark.read.parquet(str(path))
            columns = df.columns

            print(f"Columns: {len(columns)}", flush=True)
            print(f"Rows: {df.count():,}", flush=True)

            missing_summary = []

            for start in range(0, len(columns), BATCH_SIZE):
                batch = columns[start:start + BATCH_SIZE]
                expressions = []

                for i, name in enumerate(batch):
                    col = F.col(f"`{name.replace('`', '``')}`")
                    missing = (
                        col.isNull()
                        | (F.trim(col.cast("string")) == "")
                    )

                    expressions.append(
                        F.sum(
                            F.when(missing, 1).otherwise(0)
                        ).alias(f"c{i}")
                    )

                result = df.agg(*expressions).first().asDict()

                for i, name in enumerate(batch):
                    count = int(result[f"c{i}"] or 0)
                    if count > 0:
                        missing_summary.append((name, count))

                print(
                    f"Checked columns {min(start + len(batch), len(columns))}"
                    f"/{len(columns)}",
                    flush=True,
                )

            missing_summary.sort(key=lambda x: x[1], reverse=True)

            print("\nTop 15 columns with missing values:", flush=True)

            if missing_summary:
                for name, count in missing_summary[:15]:
                    print(f"{name}: {count:,}", flush=True)
            else:
                print("No missing values detected.", flush=True)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()