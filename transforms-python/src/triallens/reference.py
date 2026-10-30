"""Curated reference data: biomarker catalogue, reference ranges, code mappings.

Cut-offs are illustrative values for a research data product. They are NOT validated
clinical decision limits and must be replaced by the assay- and platform-specific
cut-offs agreed with the biomarker laboratory before productive use.
"""

from __future__ import annotations

# analyte, display_name, category, matrix, unit, description
BIOMARKER_CATALOG: list[tuple[str, str, str, str, str, str]] = [
    ("ABETA42", "Amyloid-beta 1-42", "AMYLOID", "CSF", "pg/mL", "Core amyloid marker; low CSF levels indicate amyloid deposition."),
    ("ABETA40", "Amyloid-beta 1-40", "AMYLOID", "CSF", "pg/mL", "Used to normalise Abeta42 (Abeta42/40 ratio)."),
    ("PTAU181", "Phospho-tau 181", "TAU", "CSF", "pg/mL", "Tau phosphorylated at threonine 181."),
    ("PTAU217", "Phospho-tau 217", "TAU", "PLASMA", "pg/mL", "Blood-based marker of Alzheimer's pathology."),
    ("TTAU", "Total tau", "NEURODEGENERATION", "CSF", "pg/mL", "Marker of neuronal injury."),
    ("NFL", "Neurofilament light chain", "NEURODEGENERATION", "PLASMA", "pg/mL", "Non-specific marker of axonal damage."),
    ("GFAP", "Glial fibrillary acidic protein", "GLIAL", "PLASMA", "pg/mL", "Marker of astrocytic activation."),
    ("HBA1C", "Haemoglobin A1c", "ROUTINE_LAB", "WHOLE_BLOOD", "%", "Glycaemic control (vascular risk factor)."),
    ("CREATININE", "Creatinine", "ROUTINE_LAB", "SERUM", "mg/dL", "Renal function; confounder for plasma NfL."),
    ("VITAMIN_B12", "Vitamin B12", "ROUTINE_LAB", "SERUM", "pg/mL", "Reversible cause of cognitive impairment."),
    ("TSH", "Thyroid-stimulating hormone", "ROUTINE_LAB", "SERUM", "mIU/L", "Reversible cause of cognitive impairment."),
    ("GLUCOSE", "Glucose (fasting)", "ROUTINE_LAB", "SERUM", "mg/dL", "Metabolic risk factor."),
    ("LDL_CHOLESTEROL", "LDL cholesterol", "ROUTINE_LAB", "SERUM", "mg/dL", "Vascular risk factor."),
]

# range_id, analyte, matrix, unit, lower_limit, upper_limit, note  (one range per analyte)
REFERENCE_RANGES: list[tuple[str, str, str, str, float | None, float | None, str]] = [
    ("RR-ABETA42", "ABETA42", "CSF", "pg/mL", 1030.0, None, "Illustrative cut-off; below = amyloid positive."),
    ("RR-ABETA40", "ABETA40", "CSF", "pg/mL", None, None, "No standalone cut-off; use Abeta42/40 ratio."),
    ("RR-PTAU181", "PTAU181", "CSF", "pg/mL", None, 27.0, "Illustrative cut-off."),
    ("RR-PTAU217", "PTAU217", "PLASMA", "pg/mL", None, 0.4, "Illustrative cut-off; platform specific."),
    ("RR-TTAU", "TTAU", "CSF", "pg/mL", None, 300.0, "Illustrative cut-off."),
    ("RR-NFL", "NFL", "PLASMA", "pg/mL", None, 25.0, "Age-dependent in practice; single illustrative cut-off."),
    ("RR-GFAP", "GFAP", "PLASMA", "pg/mL", None, 200.0, "Illustrative cut-off."),
    ("RR-HBA1C", "HBA1C", "WHOLE_BLOOD", "%", 4.0, 5.6, "Adult reference interval."),
    ("RR-CREATININE", "CREATININE", "SERUM", "mg/dL", 0.6, 1.3, "Adult reference interval."),
    ("RR-VITAMIN_B12", "VITAMIN_B12", "SERUM", "pg/mL", 200.0, 900.0, "Adult reference interval."),
    ("RR-TSH", "TSH", "SERUM", "mIU/L", 0.4, 4.0, "Adult reference interval."),
    ("RR-GLUCOSE", "GLUCOSE", "SERUM", "mg/dL", 70.0, 99.0, "Fasting reference interval."),
    ("RR-LDL_CHOLESTEROL", "LDL_CHOLESTEROL", "SERUM", "mg/dL", None, 130.0, "Desirable upper limit."),
]

# Routine lab LOINC codes mapped onto the harmonised analyte vocabulary.
LOINC_TO_ANALYTE: dict[str, str] = {
    "4548-4": "HBA1C",
    "2160-0": "CREATININE",
    "2132-9": "VITAMIN_B12",
    "3016-3": "TSH",
    "2345-7": "GLUCOSE",
    "13457-7": "LDL_CHOLESTEROL",
}

# Assay export spellings (after code_key normalisation) -> harmonised analyte.
ANALYTE_ALIASES: dict[str, str] = {
    "ABETA42": "ABETA42", "AB42": "ABETA42", "ABETA142": "ABETA42", "AB142": "ABETA42",
    "ABETA40": "ABETA40", "AB40": "ABETA40", "ABETA140": "ABETA40", "AB140": "ABETA40",
    "PTAU181": "PTAU181", "PTAU": "PTAU181", "PTAU181P": "PTAU181",
    "PTAU217": "PTAU217",
    "TTAU": "TTAU", "TAU": "TTAU", "TOTALTAU": "TTAU",
    "NFL": "NFL", "NFLIGHT": "NFL", "NEUROFILAMENTLIGHT": "NFL",
    "GFAP": "GFAP",
}

# Unit (after code_key normalisation, '/' removed) -> factor to pg/mL.
UNIT_TO_PG_PER_ML: dict[str, float] = {
    "PGML": 1.0,
    "NGL": 1.0,
    "NGML": 1000.0,
    "FGML": 0.001,
}

# Cognitive instruments: max score and direction.
INSTRUMENT_MAX: dict[str, float] = {"MMSE": 30.0, "MOCA": 30.0, "CDR_SB": 18.0, "ADAS_COG13": 85.0}
HIGHER_IS_BETTER: dict[str, bool] = {"MMSE": True, "MOCA": True, "CDR_SB": False, "ADAS_COG13": False}
# Illustrative impairment thresholds: impaired if score < threshold (higher-is-better)
# or score >= threshold (lower-is-better).
IMPAIRMENT_THRESHOLD: dict[str, float] = {"MMSE": 24.0, "MOCA": 26.0, "CDR_SB": 0.5, "ADAS_COG13": 17.0}

INSTRUMENT_ALIASES: dict[str, str] = {
    "MMSE": "MMSE", "MMST": "MMSE",
    "MOCA": "MOCA",
    "CDRSB": "CDR_SB", "CDRSUMOFBOXES": "CDR_SB",
    "ADASCOG13": "ADAS_COG13", "ADAS13": "ADAS_COG13",
}

# Amyloid status thresholds used for cohort features.
ABETA42_40_RATIO_POSITIVE_BELOW = 0.065
AMYLOID_PET_SUVR_POSITIVE_ABOVE = 1.11

# APOE haplotype-defining SNPs.
APOE_RS429358 = "rs429358"  # C allele -> e4
APOE_RS7412 = "rs7412"  # T allele -> e2
