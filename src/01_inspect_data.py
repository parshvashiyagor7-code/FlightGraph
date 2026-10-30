
from pathlib import Path

from pyspark.sql import SparkSession


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

FILES = [
    "train.parquet",
    "val.parquet",
    "test.parquet",
]


def main():
    spark = (
        SparkSession.builder
        .appName("FlightGraph-Data-Inspection")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        print("\nFLIGHTGRAPH DATASET INSPECTION")
        print("=" * 60)

        for filename in FILES:
            file_path = DATA_DIR / filename

            print(f"\nDataset: {filename}")
            print("-" * 60)

            if not file_path.exists():
                print(f"ERROR: File not found: {file_path}")
                continue

            df = spark.read.parquet(str(file_path))

            print("\nSchema:")
            df.printSchema()

            print(f"\nColumns: {len(df.columns)}")
            print(df.columns)

            print("\nTotal records:")
            print(f"{df.count():,}")

            print("\nFirst 5 rows:")
            df.show(5, truncate=False)

        print("\nInspection completed.")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
