from __future__ import annotations

from conftest import SALT
from triallens.logic.clinical import (
    clean_ehr_diagnoses,
    clean_ehr_encounters,
    clean_ehr_patients,
    curate_diagnoses,
    curate_patient_master,
)
from triallens.utils.pseudonymize import pseudonymize_value

PATIENT_COLUMNS = "mrn string, sex string, birth_date string, postal_code string, ethnicity string, " \
                  "deceased_date string, site_code string, last_updated string"


def test_clean_patients_keeps_latest_record_and_maps_sex(spark):
    raw = spark.createDataFrame(
        [
            ("MRN1", "weiblich", "12.03.1950", "66123", "x", "", "site-n", "2025-01-01T10:00:00"),
            ("mrn1", "W", "1950-03-12", "10115", "x", "", "SITE-N", "2025-06-01T10:00:00"),
            ("MRN2", "1", "1960-01-01", "01067", "", "", "SITE-S", "2025-02-01 08:00:00"),
            ("MRN3", "?", "1970-01-01", "80331", "", "", "", "2025-02-01 08:00:00"),  # no site -> dropped
        ],
        PATIENT_COLUMNS,
    )
    rows = {r["patient_id"]: r for r in clean_ehr_patients(raw, SALT).collect()}
    assert set(rows) == {pseudonymize_value("MRN1", SALT), pseudonymize_value("MRN2", SALT)}
    latest = rows[pseudonymize_value("MRN1", SALT)]
    assert latest["sex"] == "F"
    assert latest["postal_region"] == "10"  # from the most recent record
    assert latest["birth_year"] == 1950
    assert rows[pseudonymize_value("MRN2", SALT)]["postal_region"] == "01"


def test_patient_master_drops_identifying_fields(spark):
    raw = spark.createDataFrame([("MRN1", "M", "1950-03-12", "66123", "WHITE", "", "SITE-N", "2025-01-01")], PATIENT_COLUMNS)
    encounters = spark.createDataFrame(
        [("E1", "MRN1", "AMB", "2023-01-02T09:00:00", "2023-01-02T10:00:00", "SITE-N", "Neuro")],
        "encounter_id string, mrn string, encounter_type string, admit_ts string, discharge_ts string, "
        "site_code string, department string",
    )
    master = curate_patient_master(clean_ehr_patients(raw, SALT), clean_ehr_encounters(encounters, SALT))
    assert not {"birth_date", "postal_code", "ethnicity", "mrn"} & set(master.columns)
    row = master.first()
    assert row["n_encounters"] == 1
    assert row["age_band"] in ("70-79", "80+")


def test_encounter_with_discharge_before_admission_keeps_admission(spark):
    raw = spark.createDataFrame(
        [("E1", "MRN1", "STAT", "2023-01-02T09:00:00", "2023-01-01T09:00:00", "SITE-N", "Neuro")],
        "encounter_id string, mrn string, encounter_type string, admit_ts string, discharge_ts string, "
        "site_code string, department string",
    )
    row = clean_ehr_encounters(raw, SALT).first()
    assert row["encounter_type"] == "INPATIENT"
    assert row["discharge_ts"] is None


def test_icd10_normalisation_and_disease_groups(spark):
    raw = spark.createDataFrame(
        [
            ("D1", "E1", "MRN1", "g301", "2023-01-02", "Y"),
            ("D2", "E1", "MRN1", "F00.1*", "2023-01-02", "N"),
            ("D3", "E1", "MRN1", "G31.82", "2023-01-02", ""),
            ("D4", "E1", "MRN1", "G310", "2023-01-02", ""),
            ("D5", "E1", "MRN1", "I10", "2023-01-02", ""),
            ("D6", "E1", "MRN1", "???", "2023-01-02", ""),  # invalid -> dropped
        ],
        "diagnosis_id string, encounter_id string, mrn string, icd10_code string, diagnosis_date string, is_primary string",
    )
    rows = {r["diagnosis_id"]: r for r in curate_diagnoses(clean_ehr_diagnoses(raw, SALT)).collect()}
    assert set(rows) == {"D1", "D2", "D3", "D4", "D5"}
    assert (rows["D1"]["icd10_code"], rows["D1"]["diagnosis_group"], rows["D1"]["is_primary"]) == ("G30.1", "ALZHEIMERS", True)
    assert rows["D2"]["icd10_code"] == "F00.1"
    assert rows["D3"]["diagnosis_group"] == "DLB"
    assert rows["D4"]["diagnosis_group"] == "FTD"
    assert (rows["D5"]["diagnosis_group"], rows["D5"]["icd10_chapter"]) == ("OTHER", "Circulatory system")
