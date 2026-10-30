"""EHR domain: patients, encounters, diagnoses, medications."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from triallens.utils.columns import (
    age_band,
    clean_str,
    code_key,
    latest_per_key,
    map_values,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_timestamp,
    upper_str,
)
from triallens.utils.pseudonymize import pseudonymize

SEX_MAP = {
    "M": "M", "MALE": "M", "MAENNLICH": "M", "MANNLICH": "M", "1": "M",
    "F": "F", "W": "F", "FEMALE": "F", "WEIBLICH": "F", "2": "F",
    "X": "X", "D": "X", "DIVERS": "X", "DIVERSE": "X",
}

ENCOUNTER_TYPE_MAP = {
    "OUTPATIENT": "OUTPATIENT", "AMB": "OUTPATIENT", "AMBULANT": "OUTPATIENT",
    "INPATIENT": "INPATIENT", "STAT": "INPATIENT", "STATIONAER": "INPATIENT",
    "EMERGENCY": "EMERGENCY", "ER": "EMERGENCY", "NOTAUFNAHME": "EMERGENCY",
    "TELEHEALTH": "TELEHEALTH", "VIDEO": "TELEHEALTH", "TELE": "TELEHEALTH",
}

ICD10_PATTERN = r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$"
ATC_PATTERN = r"^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$"

# Order matters: the first matching prefix wins.
DIAGNOSIS_GROUP_PREFIXES: list[tuple[str, str]] = [
    ("G30", "ALZHEIMERS"),
    ("F00", "ALZHEIMERS"),
    ("G31.82", "DLB"),
    ("G31.0", "FTD"),
    ("F02.0", "FTD"),
    ("G20", "PARKINSONS"),
    ("G12.2", "ALS"),
    ("F06.7", "MCI"),
    ("F01", "VASCULAR_DEMENTIA"),
]

ICD10_CHAPTERS: dict[str, str] = {
    "A": "Infectious diseases", "B": "Infectious diseases",
    "C": "Neoplasms", "D": "Neoplasms / blood",
    "E": "Endocrine and metabolic", "F": "Mental and behavioural",
    "G": "Nervous system", "H": "Eye and ear",
    "I": "Circulatory system", "J": "Respiratory system",
    "K": "Digestive system", "L": "Skin", "M": "Musculoskeletal",
    "N": "Genitourinary", "O": "Pregnancy", "P": "Perinatal",
    "Q": "Congenital", "R": "Symptoms and findings",
    "S": "Injury", "T": "Injury and poisoning",
    "V": "External causes", "W": "External causes", "X": "External causes", "Y": "External causes",
    "Z": "Health status and services", "U": "Special purposes",
}


# --------------------------------------------------------------------------- clean


def clean_ehr_patients(patients: DataFrame, salt: str) -> DataFrame:
    typed = patients.select(
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        map_values(code_key("sex"), SEX_MAP, "U").alias("sex"),
        parse_date("birth_date").alias("birth_date"),
        clean_str("postal_code").alias("postal_code"),
        upper_str("ethnicity").alias("ethnicity"),
        parse_date("deceased_date").alias("deceased_date"),
        upper_str("site_code").alias("site_code"),
        parse_timestamp("last_updated").alias("last_updated"),
    ).where(F.col("patient_id").isNotNull() & F.col("site_code").isNotNull())

    latest = latest_per_key(typed, ["patient_id"], "last_updated")
    return latest.select(
        "patient_id",
        "sex",
        "birth_date",
        F.year("birth_date").alias("birth_year"),
        F.when(F.col("postal_code").rlike("^[0-9]{5}$"), F.substring("postal_code", 1, 2)).alias("postal_region"),
        "ethnicity",
        "deceased_date",
        "site_code",
        "last_updated",
    )


def clean_ehr_encounters(encounters: DataFrame, salt: str) -> DataFrame:
    typed = encounters.select(
        clean_str("encounter_id").alias("encounter_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        map_values(code_key("encounter_type"), ENCOUNTER_TYPE_MAP, "OTHER").alias("encounter_type"),
        parse_timestamp("admit_ts").alias("admit_ts"),
        parse_timestamp("discharge_ts").alias("discharge_ts"),
        upper_str("site_code").alias("site_code"),
        clean_str("department").alias("department"),
    ).where(
        F.col("encounter_id").isNotNull() & F.col("patient_id").isNotNull() & F.col("admit_ts").isNotNull()
    )
    # A discharge before admission is a known EHR artefact: drop the discharge, keep the encounter.
    fixed = typed.withColumn(
        "discharge_ts",
        F.when(F.col("discharge_ts") >= F.col("admit_ts"), F.col("discharge_ts")),
    )
    return latest_per_key(fixed, ["encounter_id"], "admit_ts")


def normalize_icd10(c: str | Column) -> Column:
    """``g301`` / ``G30.1`` / ``G30.1*`` -> ``G30.1``."""
    raw = F.upper(F.regexp_replace(clean_str(c), "[^A-Za-z0-9.]", ""))
    return F.when(
        raw.rlike("^[A-Z][0-9]{2}[0-9A-Z]+$"),
        F.concat(F.substring(raw, 1, 3), F.lit("."), F.substring(raw, 4, 10)),
    ).otherwise(raw)


def clean_ehr_diagnoses(diagnoses: DataFrame, salt: str) -> DataFrame:
    typed = diagnoses.select(
        clean_str("diagnosis_id").alias("diagnosis_id"),
        clean_str("encounter_id").alias("encounter_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        normalize_icd10("icd10_code").alias("icd10_code"),
        parse_date("diagnosis_date").alias("diagnosis_date"),
        F.coalesce(parse_bool("is_primary"), F.lit(False)).alias("is_primary"),
    ).where(
        F.col("diagnosis_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("diagnosis_date").isNotNull()
        & F.col("icd10_code").rlike(ICD10_PATTERN)
    )
    return typed.dropDuplicates(["diagnosis_id"])


def clean_ehr_medications(medications: DataFrame, salt: str) -> DataFrame:
    dose = parse_decimal("dose_mg")
    typed = medications.select(
        clean_str("medication_id").alias("medication_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        F.regexp_replace(upper_str("atc_code"), r"\s", "").alias("atc_code"),
        F.initcap(clean_str("drug_name")).alias("drug_name"),
        parse_date("start_date").alias("start_date"),
        parse_date("end_date").alias("end_date"),
        F.when((dose >= 0) & (dose <= 5000), dose).alias("dose_mg"),
        upper_str("route").alias("route"),
    ).where(
        F.col("medication_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("start_date").isNotNull()
        & F.col("atc_code").rlike(ATC_PATTERN)
    )
    return typed.dropDuplicates(["medication_id"])


# ------------------------------------------------------------------------- curated


def diagnosis_group(icd10_code: Column) -> Column:
    expr = None
    for prefix, group in DIAGNOSIS_GROUP_PREFIXES:
        condition = icd10_code.startswith(prefix)
        expr = F.when(condition, group) if expr is None else expr.when(condition, group)
    return expr.otherwise("OTHER")


def curate_diagnoses(diagnoses: DataFrame) -> DataFrame:
    return diagnoses.select(
        "diagnosis_id",
        "encounter_id",
        "patient_id",
        "icd10_code",
        map_values(F.substring("icd10_code", 1, 1), ICD10_CHAPTERS, "Unclassified").alias("icd10_chapter"),
        diagnosis_group(F.col("icd10_code")).alias("diagnosis_group"),
        "diagnosis_date",
        "is_primary",
    )


def curate_encounter_timeline(encounters: DataFrame) -> DataFrame:
    return encounters.select(
        "encounter_id",
        "patient_id",
        "encounter_type",
        "admit_ts",
        "discharge_ts",
        F.datediff(F.to_date("discharge_ts"), F.to_date("admit_ts")).alias("length_of_stay_days"),
        "site_code",
        "department",
    )


def curate_patient_master(patients: DataFrame, encounters: DataFrame) -> DataFrame:
    """Analysis-ready patient table.

    GDPR data minimisation: birth date is reduced to birth year and age band, postal
    code to its 2-digit region, and ethnicity (Art. 9 special category) does not leave
    the restricted clean layer.
    """
    encounter_stats = encounters.groupBy("patient_id").agg(
        F.count("*").alias("n_encounters"),
        F.min(F.to_date("admit_ts")).alias("first_encounter_date"),
        F.max(F.to_date("admit_ts")).alias("last_encounter_date"),
    )
    reference_date = F.coalesce(F.col("deceased_date"), F.current_date())
    age = F.floor(F.months_between(reference_date, F.col("birth_date")) / 12).cast("int")
    return (
        patients.join(encounter_stats, "patient_id", "left")
        .select(
            "patient_id",
            "sex",
            "birth_year",
            age.alias("age_years"),
            age_band(age).alias("age_band"),
            "postal_region",
            F.col("deceased_date").isNotNull().alias("is_deceased"),
            F.col("site_code").alias("home_site_code"),
            F.coalesce(F.col("n_encounters"), F.lit(0)).cast("int").alias("n_encounters"),
            "first_encounter_date",
            "last_encounter_date",
        )
    )
