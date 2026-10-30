
from pathlib import Path
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "raw" / "train.parquet"

spark = (
    SparkSession.builder
    .appName("FlightGraph-ETL-Schema-Check")
    .master("local[2]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

try:
    df = spark.read.parquet(str(DATA))

    candidates = [
        "FlightDate",
        "date",
        "Year",
        "Month",
        "DayofMonth",
        "DayOfWeek",
        "Origin",
        "Dest",
        "Reporting_Airline",
        "ArrDel15",
    ]

    print("\nCOLUMN TYPES")
    print("=" * 45)

    for name in candidates:
        if name in df.columns:
            print(f"{name}: {df.schema[name].dataType.simpleString()}")

    available = [name for name in candidates if name in df.columns]

    print("\nSAMPLE VALUES")
    print("=" * 45)

    df.select(*available).show(5, truncate=False)

finally:
    spark.stop()
