"""Patient-level feature table that powers the cohort builder and the Patient object."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from triallens.logic.omics import derive_apoe
from triallens.reference import ABETA42_40_RATIO_POSITIVE_BELOW, AMYLOID_PET_SUVR_POSITIVE_ABOVE
from triallens.utils.columns import latest_per_key

COGNITIVE_FEATURES = {"MMSE": "latest_mmse", "MOCA": "latest_moca", "CDR_SB": "latest_cdr_sb"}
BIOMARKER_FEATURES = {
    "ABETA42": "latest_abeta42",
    "ABETA40": "latest_abeta40",
    "PTAU181": "latest_ptau181",
    "PTAU217": "latest_ptau217",
    "NFL": "latest_nfl",
    "GFAP": "latest_gfap",
}


def _latest_values(df: DataFrame, key_col: str, date_col: str, mapping: dict[str, str]) -> DataFrame:
    latest = latest_per_key(df.where(F.col(key_col).isin(*mapping)), ["patient_id", key_col], date_col)
    return latest.groupBy("patient_id").agg(
        *[F.max(F.when(F.col(key_col) == key, F.col("value"))).alias(name) for key, name in mapping.items()]
    )


def curate_cohort_features(
    patients: DataFrame,
    diagnoses: DataFrame,
    cognitive: DataFrame,
    biomarkers: DataFrame,
    imaging: DataFrame,
    omics: DataFrame,
    genotypes: DataFrame,
    participation: DataFrame,
    specimens: DataFrame,
) -> DataFrame:
    primary_dx = (
        latest_per_key(
            diagnoses.where(F.col("diagnosis_group") != "OTHER").withColumn(
                "_rank_date", F.when(F.col("is_primary"), F.date_add("diagnosis_date", 36500)).otherwise(F.col("diagnosis_date"))
            ),
            ["patient_id"],
            "_rank_date",
        )
        .select("patient_id", F.col("diagnosis_group").alias("primary_diagnosis_group"))
    )

    cognition = _latest_values(
        cognitive.withColumnRenamed("score", "value"), "instrument", "assessed_date", COGNITIVE_FEATURES
    )
    fluid = _latest_values(
        biomarkers.where(F.col("qc_status") != "FAIL"), "analyte", "measured_date", BIOMARKER_FEATURES
    )

    imaging_flags = imaging.groupBy("patient_id").agg(
        F.max((F.col("modality") == "MR").cast("int")).alias("_mri"),
        F.max((F.col("modality") == "PT").cast("int")).alias("_pet"),
        F.max("amyloid_suvr").alias("_max_suvr"),
    )
    specimen_flags = specimens.groupBy("patient_id").agg(
        F.max((F.col("specimen_type") == "CSF").cast("int")).alias("_csf"),
    )
    omics_flags = omics.groupBy("patient_id").agg(
        F.max(
            (F.col("assay_type").isin("WGS", "GENOTYPING_ARRAY") & F.col("qc_pass")).cast("int")
        ).alias("_genetics"),
    )
    apoe = derive_apoe(genotypes, omics)
    study_flags = participation.groupBy("patient_id").agg(
        F.countDistinct(
            F.when(F.col("status").isin("ENROLLED", "COMPLETED"), F.col("study_code"))
        ).alias("n_studies"),
        F.max(F.col("consent_genetics").cast("int")).alias("_consent_genetics"),
        F.max(F.col("is_consent_valid").cast("int")).alias("_consent_research"),
    )

    joined = patients
    for frame in (primary_dx, cognition, fluid, imaging_flags, specimen_flags, omics_flags, apoe, study_flags):
        joined = joined.join(frame, "patient_id", "left")

    ratio = F.col("latest_abeta42") / F.col("latest_abeta40")
    amyloid_status = (
        F.when((ratio < ABETA42_40_RATIO_POSITIVE_BELOW) | (F.col("_max_suvr") > AMYLOID_PET_SUVR_POSITIVE_ABOVE), "POSITIVE")
        .when(ratio.isNotNull() | F.col("_max_suvr").isNotNull(), "NEGATIVE")
        .otherwise("UNKNOWN")
    )

    def flag(column: str):
        return F.coalesce(F.col(column) == 1, F.lit(False))

    consent_research = flag("_consent_research")
    return joined.select(
        "patient_id",
        "sex",
        "birth_year",
        "age_years",
        "age_band",
        "postal_region",
        "home_site_code",
        "is_deceased",
        F.coalesce(F.col("primary_diagnosis_group"), F.lit("NONE")).alias("primary_diagnosis_group"),
        "latest_mmse",
        "latest_moca",
        "latest_cdr_sb",
        F.round(ratio, 4).alias("latest_abeta42_40_ratio"),
        "latest_ptau181",
        "latest_ptau217",
        "latest_nfl",
        "latest_gfap",
        amyloid_status.alias("amyloid_status"),
        flag("_csf").alias("has_csf"),
        flag("_mri").alias("has_mri"),
        flag("_pet").alias("has_pet"),
        flag("_genetics").alias("has_genetics"),
        "apoe_genotype",
        "apoe_e4_carrier",
        F.coalesce(F.col("n_studies"), F.lit(0)).cast("int").alias("n_studies"),
        flag("_consent_genetics").alias("consent_genetics"),
        consent_research.alias("consent_research"),
        (consent_research & ~F.col("is_deceased")).alias("eligible_for_research"),
    )
