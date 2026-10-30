"""Declarative DAG of the raw -> clean -> curated layers.

The same spec drives the Foundry transforms (triallens/foundry/step_transforms.py) and
the local runner (triallens/local/runner.py), so lineage in Foundry and in CI is
identical by construction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pyspark.sql import DataFrame

from triallens.datasets import name_of
from triallens.logic import clinical, cognition, cohort, imaging, lab, omics, specimens, study


@dataclass(frozen=True)
class Step:
    output: str  # logical dataset name, e.g. "clean/ehr_patients_clean"
    fn: Callable[..., DataFrame]
    inputs: dict[str, str] = field(default_factory=dict)  # fn parameter -> logical dataset
    needs_salt: bool = False
    description: str = ""

    @property
    def name(self) -> str:
        return name_of(self.output)


STEPS: tuple[Step, ...] = (
    # ----------------------------------------------------------------- clean (14)
    Step("clean/ehr_patients_clean", clinical.clean_ehr_patients, {"patients": "raw/ehr_patients"}, True,
         "Typed, de-duplicated (latest record wins), pseudonymised patient demographics."),
    Step("clean/ehr_encounters_clean", clinical.clean_ehr_encounters, {"encounters": "raw/ehr_encounters"}, True,
         "Encounters with harmonised encounter types."),
    Step("clean/ehr_diagnoses_clean", clinical.clean_ehr_diagnoses, {"diagnoses": "raw/ehr_diagnoses"}, True,
         "Diagnoses with normalised ICD-10-GM codes."),
    Step("clean/ehr_medications_clean", clinical.clean_ehr_medications, {"medications": "raw/ehr_medications"}, True,
         "Medication orders with validated ATC codes."),
    Step("clean/lab_results_clean", lab.clean_lab_results, {"lab_results": "raw/lab_results"}, True,
         "Routine lab results; decimal commas and censored values handled."),
    Step("clean/lims_specimens_clean", specimens.clean_lims_specimens, {"specimens": "raw/lims_specimens"}, True,
         "Biobank inventory with harmonised specimen types and storage locations."),
    Step("clean/biomarker_assays_clean", lab.clean_biomarker_assays, {"assays": "raw/biomarker_assays"}, False,
         "Fluid biomarker results harmonised to pg/mL."),
    Step("clean/imaging_series_clean", imaging.clean_imaging_series, {"dicom": "raw/imaging_dicom_metadata"}, True,
         "One row per DICOM series."),
    Step("clean/imaging_measures_clean", imaging.clean_imaging_measures, {"measures": "raw/imaging_derived_measures"}, False,
         "Derived imaging measures with semantic versions."),
    Step("clean/omics_samples_clean", omics.clean_omics_samples, {"manifest": "raw/omics_sample_manifest"}, False,
         "Omics sample manifest with validated file checksums."),
    Step("clean/omics_genotypes_clean", omics.clean_omics_genotypes, {"genotypes": "raw/omics_genotypes"}, False,
         "Targeted genotype calls in unphased, sorted-allele form."),
    Step("clean/cognitive_assessments_clean", cognition.clean_cognitive_assessments,
         {"assessments": "raw/cognitive_assessments"}, True, "Cognitive scores within instrument scales."),
    Step("clean/ctms_enrollment_clean", study.clean_ctms_enrollment, {"enrollment": "raw/ctms_enrollment"}, True,
         "Study enrollment with harmonised status."),
    Step("clean/consent_registry_clean", study.clean_consent_registry, {"consents": "raw/consent_registry"}, True,
         "Consent records per scope with an is_active flag."),
    # --------------------------------------------------------------- curated (10)
    Step("curated/patient_master", clinical.curate_patient_master,
         {"patients": "clean/ehr_patients_clean", "encounters": "clean/ehr_encounters_clean"},
         description="Data-minimised patient table (birth year, age band, 2-digit postal region)."),
    Step("curated/encounter_timeline", clinical.curate_encounter_timeline,
         {"encounters": "clean/ehr_encounters_clean"}, description="Encounters with length of stay."),
    Step("curated/diagnosis_curated", clinical.curate_diagnoses,
         {"diagnoses": "clean/ehr_diagnoses_clean"}, description="Diagnoses with ICD chapter and disease group."),
    Step("curated/specimen_inventory", specimens.curate_specimen_inventory,
         {"specimens": "clean/lims_specimens_clean"}, description="Specimens with pre-analytical processing delay."),
    Step("curated/biomarker_timeseries", lab.curate_biomarker_timeseries,
         {"assays": "clean/biomarker_assays_clean", "lab_results": "clean/lab_results_clean",
          "specimens": "clean/lims_specimens_clean"},
         description="All biomarker and routine-lab measurements per patient with reference-range flags."),
    Step("curated/imaging_studies", imaging.curate_imaging_studies,
         {"series": "clean/imaging_series_clean", "measures": "clean/imaging_measures_clean"},
         description="Imaging series with hippocampal volume, amyloid SUVR and cortical thickness."),
    Step("curated/omics_samples", omics.curate_omics_samples,
         {"samples": "clean/omics_samples_clean", "specimens": "clean/lims_specimens_clean"},
         description="Omics samples linked to patients via biobank specimens."),
    Step("curated/cognitive_scores", cognition.curate_cognitive_scores,
         {"assessments": "clean/cognitive_assessments_clean"},
         description="Cognitive scores normalised across instruments with impairment flags."),
    Step("curated/study_participation", study.curate_study_participation,
         {"enrollment": "clean/ctms_enrollment_clean", "consents": "clean/consent_registry_clean"},
         description="Enrollment with current consent state per scope."),
    Step("curated/cohort_features", cohort.curate_cohort_features,
         {"patients": "curated/patient_master", "diagnoses": "curated/diagnosis_curated",
          "cognitive": "curated/cognitive_scores", "biomarkers": "curated/biomarker_timeseries",
          "imaging": "curated/imaging_studies", "omics": "curated/omics_samples",
          "genotypes": "clean/omics_genotypes_clean", "participation": "curated/study_participation",
          "specimens": "curated/specimen_inventory"},
         description="One row per patient with every feature the cohort builder filters on."),
)


def step_outputs() -> list[str]:
    return [s.output for s in STEPS]


def validate_dag(raw_inputs: list[str]) -> None:
    """Every input must be a raw source or produced by an earlier step."""
    available = set(raw_inputs)
    for step in STEPS:
        missing = [d for d in step.inputs.values() if d not in available]
        if missing:
            raise ValueError(f"{step.output} depends on unavailable datasets {missing}")
        if step.output in available:
            raise ValueError(f"{step.output} is produced twice")
        available.add(step.output)
