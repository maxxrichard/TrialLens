# MVP plan (6 weeks)

| Week | Scope | Exit criterion |
|---|---|---|
| 1 | Data Connection syncs for EHR, LIMS, assay exports, CTMS, eCRF; restricted raw project; salt dataset | raw datasets refreshing on schedule |
| 2 | Clean layer for the MVP sources with pseudonymisation and expectations | expectations green on real data |
| 3 | Curated `patient_master`, `biomarker_timeseries`, `cognitive_scores`, `study_participation`, `cohort_features` | features reviewed with clinical lead |
| 4 | Core ontology (Patient, Encounter, Diagnosis, BiomarkerMeasurement, Specimen, Study, Enrollment, Cohort...) and markings | object access tested per user group |
| 5 | Cohort Builder (criteria functions, funnel, create cohort action) | three real feasibility questions answered by users |
| 6 | Hardening: CI, branch builds, release process, user onboarding | v1.0.0 promoted to production |

**Out of MVP scope** (delivered in later releases, see CHANGELOG): omics and imaging
derived measures, Biomarker Review, Data Quality dashboard, AIP Logic flows, Specimen
Tracker, Study Operations.
