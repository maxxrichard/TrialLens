from __future__ import annotations

import pytest

from conftest import SALT
from triallens.logic.lab import clean_biomarker_assays, clean_lab_results, curate_biomarker_timeseries
from triallens.logic.omics import clean_omics_genotypes, derive_apoe
from triallens.logic.specimens import clean_lims_specimens

ASSAY_COLUMNS = "assay_result_id string, specimen_barcode string, run_id string, plate_id string, platform string, " \
                "analyte string, value string, unit string, lloq string, uloq string, run_date string, qc_status string"
SPECIMEN_COLUMNS = "specimen_barcode string, parent_barcode string, mrn string, specimen_type string, " \
                   "collected_ts string, received_ts string, freezer_id string, rack string, box string, " \
                   "position string, volume_ul string, shipment_id string, status string"
LAB_COLUMNS = "result_id string, mrn string, specimen_barcode string, loinc_code string, test_name string, " \
              "value string, unit string, collected_ts string, resulted_ts string, abnormal_flag string"


def _assays(spark):
    return spark.createDataFrame(
        [
            ("A1", "spc1-a1", "R1", "P1", "Lumipulse", "Abeta1-42", "0,65", "ng/mL", "0.2", "1.7", "2023-02-01", "OK"),
            ("A2", "SPC1-A1", "R1", "P1", "Lumipulse", "AB40", "12000", "pg/mL", "1000", "40000", "2023-02-01", "PASS"),
            ("A3", "SPC1-A1", "R1", "P1", "Lumipulse", "p-tau181", "130", "pg/mL", "8", "120", "2023-02-01", "failed"),
            ("A4", "SPC9-A1", "R1", "P1", "Lumipulse", "unknown analyte", "1", "pg/mL", "", "", "2023-02-01", "PASS"),
            ("A5", "SPC404", "R1", "P1", "Simoa", "NfL", "12", "pg/mL", "0.5", "500", "2023-02-01", "PASS"),
        ],
        ASSAY_COLUMNS,
    )


def _specimens(spark):
    return spark.createDataFrame(
        [
            ("SPC1", "", "MRN1", "Liquor", "2023-01-10T09:00:00", "2023-01-10T12:30:00", "", "", "", "", "10000", "", "DEPLETED"),
            ("SPC1-A1", "SPC1", "MRN1", "CSF", "2023-01-10T09:00:00", "2023-01-10T12:30:00", "frz-01", "R01", "B001", "A1", "500", "", "Stored"),
            ("SPC2", "", "MRN1", "Serum", "2023-01-10T09:00:00", "2023-01-10T10:00:00", "FRZ-02", "R02", "B002", "B1", "2000", "", "AVAILABLE"),
        ],
        SPECIMEN_COLUMNS,
    )


def test_clean_assays_harmonises_units_and_analytes(spark):
    rows = {r["assay_result_id"]: r for r in clean_biomarker_assays(_assays(spark)).collect()}
    assert set(rows) == {"A1", "A2", "A3", "A5"}  # unknown analyte dropped
    assert rows["A1"]["analyte"] == "ABETA42"
    assert rows["A1"]["value"] == pytest.approx(650.0)
    assert rows["A1"]["lloq"] == pytest.approx(200.0)
    assert rows["A1"]["unit"] == "pg/mL"
    assert rows["A3"]["qc_status"] == "FAIL"


def test_clean_specimens_builds_storage_location(spark):
    rows = {r["specimen_id"]: r for r in clean_lims_specimens(_specimens(spark), SALT).collect()}
    assert rows["SPC1"]["specimen_type"] == "CSF"
    assert rows["SPC1"]["status"] == "CONSUMED"
    assert rows["SPC1"]["storage_location_id"] is None
    assert rows["SPC1-A1"]["storage_location_id"] == "FRZ-01/R01/B001"
    assert rows["SPC1-A1"]["status"] == "AVAILABLE"


def test_biomarker_timeseries_flags(spark):
    labs = spark.createDataFrame(
        [
            ("L1", "MRN1", "SPC2", "3016-3", "TSH", "<0,01", "mIU/L", "2023-01-10T09:00:00", "2023-01-10T15:00:00", "L"),
            ("L2", "MRN1", "SPC2", "718-7", "Hemoglobin", "13,5", "g/dL", "2023-01-10T09:00:00", "2023-01-10T15:00:00", ""),
        ],
        LAB_COLUMNS,
    )
    series = curate_biomarker_timeseries(
        clean_biomarker_assays(_assays(spark)),
        clean_lab_results(labs, SALT),
        clean_lims_specimens(_specimens(spark), SALT),
    )
    rows = {r["measurement_id"]: r for r in series.collect()}
    # A5 references a barcode unknown to the LIMS; L2 is a lab test outside the analyte vocabulary.
    assert set(rows) == {"ASSAY-A1", "ASSAY-A2", "ASSAY-A3", "LAB-L1"}
    assert rows["ASSAY-A1"]["is_abnormal"] is True  # 650 < 1030 pg/mL
    assert rows["ASSAY-A1"]["specimen_type"] == "CSF"
    assert rows["ASSAY-A3"]["above_uloq"] is True
    assert rows["LAB-L1"]["below_lloq"] is True
    assert rows["LAB-L1"]["analyte"] == "TSH"
    assert rows["LAB-L1"]["days_since_baseline"] == 0


@pytest.mark.parametrize(
    ("rs429358", "rs7412", "expected", "carrier"),
    [
        ("T/T", "C/C", "e3/e3", False),
        ("C|T", "C/C", "e3/e4", True),
        ("C/C", "C/C", "e4/e4", True),
        ("T/T", "T/C", "e2/e3", False),
        ("T/C", "C/T", "e2/e4", True),
    ],
)
def test_apoe_haplotypes(spark, rs429358, rs7412, expected, carrier):
    genotypes = spark.createDataFrame(
        [("C1", "OMX1", "APOE", "rs429358", rs429358, "99"), ("C2", "OMX1", "APOE", "rs7412", rs7412, "99")],
        "call_id string, omics_sample_id string, gene string, variant_id string, genotype string, quality string",
    )
    samples = spark.createDataFrame([("OMX1", "P1", True)], "omics_sample_id string, patient_id string, qc_pass boolean")
    row = derive_apoe(clean_omics_genotypes(genotypes), samples).first()
    assert (row["apoe_genotype"], row["apoe_e4_carrier"]) == (expected, carrier)
