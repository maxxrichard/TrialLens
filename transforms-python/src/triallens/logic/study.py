"""Study operations: CTMS enrollment and the eConsent registry."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from triallens.utils.columns import (
    clean_str,
    latest_per_key,
    map_values,
    normalize_study_code,
    parse_bool,
    parse_date,
    upper_str,
)
from triallens.utils.pseudonymize import pseudonymize

ENROLLMENT_STATUS_MAP = {
    "SCREENING": "SCREENING", "PRESCREENING": "SCREENING",
    "SCREEN_FAILED": "SCREEN_FAILED", "SCREEN_FAIL": "SCREEN_FAILED", "SCREENFAIL": "SCREEN_FAILED",
    "SCREEN_FAILURE": "SCREEN_FAILED",
    "ENROLLED": "ENROLLED", "ACTIVE": "ENROLLED", "RANDOMIZED": "ENROLLED", "ON_STUDY": "ENROLLED",
    "COMPLETED": "COMPLETED", "COMPLETE": "COMPLETED",
    "WITHDRAWN": "WITHDRAWN", "DROPPED": "WITHDRAWN", "DROPOUT": "WITHDRAWN",
}

CONSENT_SCOPE_MAP = {
    "CLINICAL_DATA": "CLINICAL_DATA", "CLINICAL": "CLINICAL_DATA",
    "BIOSAMPLES": "BIOSAMPLES", "SAMPLES": "BIOSAMPLES", "BIOBANK": "BIOSAMPLES",
    "GENETICS": "GENETICS", "GENETIC": "GENETICS", "GENETIC_ANALYSIS": "GENETICS",
    "IMAGING": "IMAGING",
    "RECONTACT": "RECONTACT", "RE_CONTACT": "RECONTACT",
}
CONSENT_SCOPES = ("CLINICAL_DATA", "BIOSAMPLES", "GENETICS", "IMAGING", "RECONTACT")
# Scopes without which a participant's data must not be used in TrialLens analyses.
REQUIRED_SCOPES = ("CLINICAL_DATA", "BIOSAMPLES")


def _token(column: str):
    return F.regexp_replace(F.regexp_replace(upper_str(column), "[^A-Z0-9]+", "_"), "^_|_$", "")


def clean_ctms_enrollment(enrollment: DataFrame, salt: str) -> DataFrame:
    typed = enrollment.select(
        clean_str("enrollment_id").alias("enrollment_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        normalize_study_code("study_code").alias("study_code"),
        clean_str("study_title").alias("study_title"),
        _token("study_phase").alias("study_phase"),
        upper_str("arm").alias("arm"),
        upper_str("site_code").alias("site_code"),
        clean_str("site_name").alias("site_name"),
        parse_date("enrolled_date").alias("enrolled_date"),
        map_values(_token("status"), ENROLLMENT_STATUS_MAP, "UNKNOWN").alias("status"),
        parse_date("withdrawn_date").alias("withdrawn_date"),
    ).where(
        F.col("enrollment_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("study_code").isNotNull()
        & F.col("enrolled_date").isNotNull()
    )
    return typed.dropDuplicates(["enrollment_id"])


def clean_consent_registry(consents: DataFrame, salt: str) -> DataFrame:
    version = F.lower(clean_str("consent_version"))
    version = F.when(version.rlike("^[0-9]"), F.concat(F.lit("v"), version)).otherwise(version)
    granted = F.coalesce(parse_bool("granted"), F.lit(False))
    withdrawn = parse_date("withdrawn_date")
    typed = consents.select(
        clean_str("consent_id").alias("consent_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        normalize_study_code("study_code").alias("study_code"),
        F.when(version.rlike(r"^v[0-9]+(\.[0-9]+)?$"), version).alias("consent_version"),
        map_values(_token("scope"), CONSENT_SCOPE_MAP).alias("scope"),
        granted.alias("granted"),
        parse_date("signed_date").alias("signed_date"),
        withdrawn.alias("withdrawn_date"),
        (granted & withdrawn.isNull()).alias("is_active"),
    ).where(
        F.col("consent_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("study_code").isNotNull()
        & F.col("scope").isNotNull()
        & F.col("signed_date").isNotNull()
    )
    return typed.dropDuplicates(["consent_id"])


def curate_study_participation(enrollment: DataFrame, consents: DataFrame) -> DataFrame:
    """Enrollment joined with the *current* consent state per scope.

    The latest signed consent per (patient, study, scope) wins, so a re-consent with a
    new version or a withdrawal supersedes the earlier record.
    """
    current = latest_per_key(consents, ["patient_id", "study_code", "scope"], "signed_date")
    pivoted = current.groupBy("patient_id", "study_code").agg(
        *[
            F.max(F.when(F.col("scope") == scope, F.col("is_active").cast("int"))).alias(f"_c_{scope}")
            for scope in CONSENT_SCOPES
        ]
    )
    joined = enrollment.join(pivoted, ["patient_id", "study_code"], "left")
    consent_cols = [
        F.coalesce(F.col(f"_c_{scope}") == 1, F.lit(False)).alias(f"consent_{scope.lower()}") for scope in CONSENT_SCOPES
    ]
    result = joined.select(
        "enrollment_id",
        "patient_id",
        "study_code",
        "study_title",
        "study_phase",
        "arm",
        "site_code",
        "site_name",
        "enrolled_date",
        "status",
        "withdrawn_date",
        *consent_cols,
    )
    valid = None
    for scope in REQUIRED_SCOPES:
        condition = F.col(f"consent_{scope.lower()}")
        valid = condition if valid is None else valid & condition
    return result.withColumn("is_consent_valid", valid)
