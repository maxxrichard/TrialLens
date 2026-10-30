# Changelog

All notable changes to TrialLens. Versions follow semantic versioning: a **major** bump
for breaking ontology changes (removed properties, changed primary keys), **minor** for
new datasets, object types, actions or apps, **patch** for fixes.

## [1.4.0] - 2026-07-10

### Added
- Data-Quality Issue Explainer AIP Logic flow and record rule `MRI_MISSING_VOLUMETRICS`.
- `requestSpecimenRetrieval` action posting retrieval requests to the LIMS via webhook.
- Imaging scanner-effects SQL analysis.

### Changed
- Imaging measures: only the latest pipeline version per (series, region, metric) feeds
  `imaging_studies`.

## [1.3.0] - 2026-05-15

### Added
- Specimen Tracker and Study Operations Workshop apps.
- `Freezer`, `StorageLocation` and `Shipment` object types.
- APOE haplotype derivation (genetics-consent aware) in `cohort_features`.

## [1.2.0] - 2026-04-03

### Added
- Biomarker Review app with suggested decisions and the `reviewBiomarkerMeasurement` action.
- Data-quality dashboard, `DataQualityCheck` / `DataQualityIssue` objects and record rules.
- Cohort criteria from text (AIP Logic) with deterministic validation.

## [1.1.0] - 2026-03-06

### Added
- Omics manifest and genotype sources; imaging derived measures.
- Consent registry integration and `study_participation`.

## [1.0.0] - 2026-02-13

### Added
- MVP: EHR, lab, LIMS, biomarker assay, imaging metadata, cognitive assessment and CTMS
  sources; clean and curated layers with expectations; core ontology; Cohort Builder.
