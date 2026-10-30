"""Laboratory domain: routine lab results, fluid biomarker assays, biomarker time series."""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from triallens.reference import ANALYTE_ALIASES, LOINC_TO_ANALYTE, REFERENCE_RANGES, UNIT_TO_PG_PER_ML
from triallens.utils.columns import (
    clean_str,
    code_key,
    is_censored,
    map_values,
    parse_date,
    parse_decimal,
    parse_timestamp,
    upper_str,
)
from triallens.utils.pseudonymize import pseudonymize

LOINC_PATTERN = r"^[0-9]{1,7}-[0-9]$"

ABNORMAL_FLAG_MAP = {"H": "H", "HH": "H", "HIGH": "H", "L": "L", "LL": "L", "LOW": "L", "N": "N", "NORMAL": "N"}
QC_STATUS_MAP = {"PASS": "PASS", "OK": "PASS", "PASSED": "PASS", "WARN": "WARN", "WARNING": "WARN", "FAIL": "FAIL", "FAILED": "FAIL"}

REFERENCE_RANGE_DDL = (
    "range_id string, analyte string, matrix string, unit string, "
    "lower_limit double, upper_limit double, note string"
)


def clean_lab_results(lab_results: DataFrame, salt: str) -> DataFrame:
    typed = lab_results.select(
        clean_str("result_id").alias("result_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        upper_str("specimen_barcode").alias("specimen_id"),
        clean_str("loinc_code").alias("loinc_code"),
        clean_str("test_name").alias("test_name"),
        parse_decimal("value").alias("value"),
        is_censored("value").alias("is_censored"),
        clean_str("unit").alias("unit"),
        parse_timestamp("collected_ts").alias("collected_ts"),
        parse_timestamp("resulted_ts").alias("resulted_ts"),
        map_values(code_key("abnormal_flag"), ABNORMAL_FLAG_MAP, "N").alias("abnormal_flag"),
    ).where(
        F.col("result_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("value").isNotNull()
        & F.col("collected_ts").isNotNull()
        & F.col("loinc_code").rlike(LOINC_PATTERN)
    )
    return typed.dropDuplicates(["result_id"])


def clean_biomarker_assays(assays: DataFrame) -> DataFrame:
    """Harmonise analyte names and convert every value (and LLOQ/ULOQ) to pg/mL."""
    factor = map_values(code_key("unit"), {k: str(v) for k, v in UNIT_TO_PG_PER_ML.items()}).cast("double")
    value = parse_decimal("value") * factor
    typed = assays.select(
        clean_str("assay_result_id").alias("assay_result_id"),
        upper_str("specimen_barcode").alias("specimen_id"),
        clean_str("run_id").alias("run_id"),
        clean_str("plate_id").alias("plate_id"),
        clean_str("platform").alias("platform"),
        map_values(code_key("analyte"), ANALYTE_ALIASES).alias("analyte"),
        value.alias("value"),
        F.lit("pg/mL").alias("unit"),
        (parse_decimal("lloq") * factor).alias("lloq"),
        (parse_decimal("uloq") * factor).alias("uloq"),
        parse_date("run_date").alias("run_date"),
        # Unknown QC states are treated as WARN so that a reviewer has to look at them.
        map_values(code_key("qc_status"), QC_STATUS_MAP, "WARN").alias("qc_status"),
    ).where(
        F.col("assay_result_id").isNotNull()
        & F.col("specimen_id").isNotNull()
        & F.col("analyte").isNotNull()
        & F.col("value").isNotNull()
        & (F.col("value") >= 0)
        & (F.col("value") <= 1_000_000)
    )
    return typed.dropDuplicates(["assay_result_id"])


def reference_ranges_df(spark) -> DataFrame:
    return spark.createDataFrame(REFERENCE_RANGES, REFERENCE_RANGE_DDL)


def curate_biomarker_timeseries(assays: DataFrame, lab_results: DataFrame, specimens: DataFrame) -> DataFrame:
    """One long table of all biomarker and routine-lab measurements per patient.

    Assay results are attached to patients through the LIMS specimen inventory, so an
    assay on an unknown barcode never reaches the curated layer (it is reported by the
    specimen reconciliation in the data-quality dashboard instead).
    """
    specimen_keys = specimens.select("specimen_id", "patient_id", "specimen_type")

    assay_part = assays.join(specimen_keys, "specimen_id", "inner").select(
        F.concat(F.lit("ASSAY-"), F.col("assay_result_id")).alias("measurement_id"),
        "patient_id",
        "specimen_id",
        "specimen_type",
        "analyte",
        "value",
        "unit",
        F.col("run_date").alias("measured_date"),
        F.lit("ASSAY").alias("source"),
        "run_id",
        "platform",
        "qc_status",
        F.coalesce(F.col("value") < F.col("lloq"), F.lit(False)).alias("below_lloq"),
        F.coalesce(F.col("value") > F.col("uloq"), F.lit(False)).alias("above_uloq"),
    )

    lab_part = (
        lab_results.withColumn("analyte", map_values(F.col("loinc_code"), LOINC_TO_ANALYTE))
        .where(F.col("analyte").isNotNull())
        .join(specimen_keys.drop("patient_id"), "specimen_id", "left")
        .select(
            F.concat(F.lit("LAB-"), F.col("result_id")).alias("measurement_id"),
            "patient_id",
            "specimen_id",
            "specimen_type",
            "analyte",
            "value",
            "unit",
            F.to_date("collected_ts").alias("measured_date"),
            F.lit("LAB").alias("source"),
            F.lit(None).cast("string").alias("run_id"),
            F.lit(None).cast("string").alias("platform"),
            F.lit("PASS").alias("qc_status"),
            F.col("is_censored").alias("below_lloq"),
            F.lit(False).alias("above_uloq"),
        )
    )

    ranges = reference_ranges_df(assays.sparkSession).select("analyte", "lower_limit", "upper_limit")
    combined = assay_part.unionByName(lab_part).join(F.broadcast(ranges), "analyte", "left")

    baseline_window = Window.partitionBy("patient_id", "analyte")
    return combined.select(
        "measurement_id",
        "patient_id",
        "specimen_id",
        "specimen_type",
        "analyte",
        "value",
        "unit",
        "measured_date",
        "source",
        "run_id",
        "platform",
        "qc_status",
        "below_lloq",
        "above_uloq",
        F.coalesce(
            (F.col("value") < F.col("lower_limit")) | (F.col("value") > F.col("upper_limit")),
            F.col("value") < F.col("lower_limit"),
            F.col("value") > F.col("upper_limit"),
            F.lit(False),
        ).alias("is_abnormal"),
        F.datediff(F.col("measured_date"), F.min("measured_date").over(baseline_window)).alias(
            "days_since_baseline"
        ),
    )
