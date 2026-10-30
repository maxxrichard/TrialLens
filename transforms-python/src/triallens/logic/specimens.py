"""Biobank / LIMS domain: specimen inventory."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from triallens.utils.columns import map_values, parse_decimal, parse_timestamp, upper_str
from triallens.utils.pseudonymize import pseudonymize

SPECIMEN_TYPE_MAP = {
    "CSF": "CSF", "LIQUOR": "CSF",
    "PLASMA": "PLASMA", "EDTA_PLASMA": "PLASMA", "EDTAPLASMA": "PLASMA",
    "SERUM": "SERUM",
    "WHOLE_BLOOD": "WHOLE_BLOOD", "WHOLEBLOOD": "WHOLE_BLOOD", "BLOOD": "WHOLE_BLOOD", "EDTA_BLOOD": "WHOLE_BLOOD",
    "DNA": "DNA",
    "RNA": "RNA", "PAXGENE_RNA": "RNA",
}

STATUS_MAP = {
    "AVAILABLE": "AVAILABLE", "IN_STORAGE": "AVAILABLE", "STORED": "AVAILABLE",
    "RESERVED": "RESERVED",
    "IN_TRANSIT": "IN_TRANSIT", "SHIPPED": "IN_TRANSIT",
    "CONSUMED": "CONSUMED", "DEPLETED": "CONSUMED",
    "DISCARDED": "DISCARDED", "DESTROYED": "DISCARDED",
}


def _token(column: str):
    """Upper case, runs of non-alphanumerics collapsed to underscores (``EDTA plasma`` -> ``EDTA_PLASMA``)."""
    return F.regexp_replace(F.regexp_replace(upper_str(column), "[^A-Z0-9]+", "_"), "^_|_$", "")


def clean_lims_specimens(specimens: DataFrame, salt: str) -> DataFrame:
    volume = parse_decimal("volume_ul")
    freezer, rack, box = upper_str("freezer_id"), upper_str("rack"), upper_str("box")
    typed = specimens.select(
        upper_str("specimen_barcode").alias("specimen_id"),
        upper_str("parent_barcode").alias("parent_specimen_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        map_values(_token("specimen_type"), SPECIMEN_TYPE_MAP).alias("specimen_type"),
        parse_timestamp("collected_ts").alias("collected_ts"),
        parse_timestamp("received_ts").alias("received_ts"),
        freezer.alias("freezer_id"),
        rack.alias("rack"),
        box.alias("box"),
        upper_str("position").alias("position"),
        F.when(freezer.isNotNull() & rack.isNotNull() & box.isNotNull(), F.concat_ws("/", freezer, rack, box)).alias(
            "storage_location_id"
        ),
        F.when((volume >= 0) & (volume <= 50000), volume).alias("volume_ul"),
        upper_str("shipment_id").alias("shipment_id"),
        # Unmapped LIMS states are surfaced (and fail the status expectation) rather than guessed.
        map_values(_token("status"), STATUS_MAP, "UNKNOWN").alias("status"),
    ).where(
        F.col("specimen_id").isNotNull() & F.col("patient_id").isNotNull() & F.col("specimen_type").isNotNull()
    )
    return typed.dropDuplicates(["specimen_id"])


def curate_specimen_inventory(specimens: DataFrame) -> DataFrame:
    delay_hours = (F.unix_timestamp("received_ts") - F.unix_timestamp("collected_ts")) / 3600.0
    return specimens.select(
        "specimen_id",
        "patient_id",
        "parent_specimen_id",
        "specimen_type",
        "collected_ts",
        "received_ts",
        F.when(delay_hours >= 0, F.round(delay_hours, 2)).alias("processing_delay_hours"),
        "storage_location_id",
        "freezer_id",
        "volume_ul",
        "shipment_id",
        "status",
    )
