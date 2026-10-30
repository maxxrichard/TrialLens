"""Record-level data-quality rules.

Dataset expectations stop bad builds; record rules flag individual records that are
technically valid but need human attention (failed assay QC, pre-analytical delays,
participants without valid consent, ...). Every match becomes a DataQualityIssue
object that is triaged in the data-quality dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordRule:
    check_id: str
    code: str
    dataset: str  # logical dataset name
    condition: str  # Spark SQL boolean expression
    record_id_column: str
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    description: str


RECORD_RULES: tuple[RecordRule, ...] = (
    RecordRule(
        "RR-001", "BIOMARKER_QC_FAIL", "curated/biomarker_timeseries", "qc_status = 'FAIL'",
        "measurement_id", "HIGH", "Assay run QC failed; the value is excluded from cohort features until re-run.",
    ),
    RecordRule(
        "RR-002", "BIOMARKER_BELOW_LLOQ", "curated/biomarker_timeseries", "below_lloq",
        "measurement_id", "MEDIUM", "Value below the lower limit of quantification; report as <LLOQ.",
    ),
    RecordRule(
        "RR-003", "BIOMARKER_ABOVE_ULOQ", "curated/biomarker_timeseries", "above_uloq",
        "measurement_id", "MEDIUM", "Value above the upper limit of quantification; re-run with dilution.",
    ),
    RecordRule(
        "RR-004", "CSF_PREANALYTIC_DELAY", "curated/specimen_inventory",
        "specimen_type = 'CSF' AND parent_specimen_id IS NULL AND processing_delay_hours > 2",
        "specimen_id", "MEDIUM", "CSF processed more than 2 h after collection; amyloid values may be biased.",
    ),
    RecordRule(
        "RR-005", "ENROLLED_WITHOUT_VALID_CONSENT", "curated/study_participation",
        "status IN ('ENROLLED', 'COMPLETED') AND NOT is_consent_valid",
        "enrollment_id", "CRITICAL", "Participant enrolled without an active clinical-data and biosample consent.",
    ),
    RecordRule(
        "RR-006", "OMICS_QC_FAIL", "curated/omics_samples", "NOT qc_pass",
        "omics_sample_id", "HIGH", "Omics sample failed sequencing / genotyping QC.",
    ),
    RecordRule(
        "RR-007", "MRI_MISSING_VOLUMETRICS", "curated/imaging_studies",
        "modality = 'MR' AND upper(series_description) LIKE '%MPRAGE%' AND hippocampal_volume_mm3 IS NULL",
        "series_id", "LOW", "Structural MRI without hippocampal volumetrics; check the processing pipeline.",
    ),
)

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
