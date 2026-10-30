"""Local SparkSession configured like the Foundry Spark profile used by TrialLens."""

from __future__ import annotations

from pyspark.sql import SparkSession


def get_local_spark(app_name: str = "triallens-local") -> SparkSession:
    return (
        SparkSession.builder.master("local[2]")
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )
