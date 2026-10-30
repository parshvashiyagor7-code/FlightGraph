
from pathlib import Path
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parent.parent
TEST_PATH = ROOT / "outputs" / "spark_write_test"

spark = (
    SparkSession.builder
    .appName("FlightGraph-Spark-Write-Test")
    .master("local[2]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")

try:
    df = spark.createDataFrame(
        [(1, "success"), (2, "success"), (3, "success")],
        ["id", "status"],
    )

    df.write.mode("overwrite").parquet(str(TEST_PATH))

    result = spark.read.parquet(str(TEST_PATH))
    count = result.count()

    print("\nSPARK WRITE TEST SUCCESS")
    print(f"Rows written and read back: {count}")
    result.show(truncate=False)

finally:
    spark.stop()
