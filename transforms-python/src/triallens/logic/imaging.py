"""Imaging domain: DICOM series metadata and derived measures."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from triallens.utils.columns import (
    clean_str,
    code_key,
    latest_per_key,
    map_values,
    parse_date,
    parse_decimal,
    parse_timestamp,
    upper_str,
)
from triallens.utils.pseudonymize import pseudonymize

DICOM_UID_PATTERN = r"^[0-9]+(\.[0-9]+)*$"
MODALITY_MAP = {"MR": "MR", "MRI": "MR", "PT": "PT", "PET": "PT", "CT": "CT"}
METRIC_MAP = {
    "VOLUMEMM3": "VOLUME_MM3", "VOLUME": "VOLUME_MM3",
    "SUVR": "SUVR",
    "CORTICALTHICKNESSMM": "CORTICAL_THICKNESS_MM", "THICKNESS": "CORTICAL_THICKNESS_MM",
}
HIPPOCAMPUS_REGIONS = ("HIPPOCAMPUS_L", "HIPPOCAMPUS_R")
AMYLOID_COMPOSITE_REGION = "COMPOSITE"


def normalize_manufacturer(c: Column) -> Column:
    value = F.upper(c)
    return (
        F.when(value.contains("SIEMENS"), "SIEMENS")
        .when(value.contains("PHILIPS"), "PHILIPS")
        .when(value.startswith("GE"), "GE_HEALTHCARE")
        .otherwise(value)
    )


def clean_imaging_series(dicom: DataFrame, salt: str) -> DataFrame:
    instances = parse_decimal("num_instances").cast("int")
    typed = dicom.select(
        clean_str("series_instance_uid").alias("series_id"),
        clean_str("study_instance_uid").alias("study_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        map_values(code_key("modality"), MODALITY_MAP).alias("modality"),
        clean_str("series_description").alias("series_description"),
        parse_date("acquisition_date").alias("acquisition_date"),
        upper_str("scanner_serial").alias("scanner_id"),
        normalize_manufacturer(clean_str("manufacturer")).alias("manufacturer"),
        parse_decimal("field_strength_t").alias("field_strength_t"),
        parse_decimal("slice_thickness_mm").alias("slice_thickness_mm"),
        F.when((instances >= 1) & (instances <= 100000), instances).alias("num_instances"),
    ).where(
        F.col("series_id").rlike(DICOM_UID_PATTERN)
        & F.col("patient_id").isNotNull()
        & F.col("modality").isNotNull()
    )
    return typed.dropDuplicates(["series_id"])


def clean_imaging_measures(measures: DataFrame) -> DataFrame:
    version = F.regexp_replace(clean_str("pipeline_version"), "^[Vv]", "v")
    region = F.regexp_replace(upper_str("region"), "[^A-Z0-9]+", "_")
    typed = measures.select(
        clean_str("measure_id").alias("measure_id"),
        clean_str("series_instance_uid").alias("series_id"),
        region.alias("region"),
        map_values(code_key("metric"), METRIC_MAP).alias("metric"),
        parse_decimal("value").alias("value"),
        F.when(version.rlike(r"^v[0-9]+\.[0-9]+\.[0-9]+$"), version).alias("pipeline_version"),
        parse_timestamp("computed_ts").alias("computed_ts"),
    ).where(
        F.col("measure_id").isNotNull()
        & F.col("series_id").isNotNull()
        & F.col("metric").isNotNull()
        & F.col("value").isNotNull()
        & (F.col("value") >= 0)
        & (F.col("value") <= 2_000_000)
    )
    return typed.dropDuplicates(["measure_id"])


def curate_imaging_studies(series: DataFrame, measures: DataFrame) -> DataFrame:
    """Series-level imaging table with the key derived measures pivoted in.

    When a series was processed by several pipeline versions only the most recent
    computation per (series, region, metric) is used.
    """
    latest = latest_per_key(measures, ["series_id", "region", "metric"], "computed_ts")

    hippocampus = (
        latest.where((F.col("metric") == "VOLUME_MM3") & F.col("region").isin(*HIPPOCAMPUS_REGIONS))
        .groupBy("series_id")
        .agg(
            # Both hemispheres are required; a single hemisphere would halve the volume.
            F.when(F.countDistinct("region") == len(HIPPOCAMPUS_REGIONS), F.sum("value")).alias(
                "hippocampal_volume_mm3"
            )
        )
    )
    amyloid = (
        latest.where((F.col("metric") == "SUVR") & (F.col("region") == AMYLOID_COMPOSITE_REGION))
        .groupBy("series_id")
        .agg(F.avg("value").alias("amyloid_suvr"))
    )
    thickness = (
        latest.where(F.col("metric") == "CORTICAL_THICKNESS_MM")
        .groupBy("series_id")
        .agg(F.avg("value").alias("mean_cortical_thickness_mm"))
    )

    return (
        series.join(hippocampus, "series_id", "left")
        .join(amyloid, "series_id", "left")
        .join(thickness, "series_id", "left")
        .select(
            "series_id",
            "study_id",
            "patient_id",
            "modality",
            "series_description",
            "acquisition_date",
            "scanner_id",
            "manufacturer",
            "field_strength_t",
            "slice_thickness_mm",
            "num_instances",
            F.round("hippocampal_volume_mm3", 1).alias("hippocampal_volume_mm3"),
            F.round("amyloid_suvr", 3).alias("amyloid_suvr"),
            F.round("mean_cortical_thickness_mm", 3).alias("mean_cortical_thickness_mm"),
        )
    )
