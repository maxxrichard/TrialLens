# Success criteria

Agreed with the domain leads at the end of discovery. Each criterion has an owner and a
way to measure it from platform data (usage metrics, action log, Data Health).

| # | Criterion | Target | Measured by |
|---|---|---|---|
| 1 | Feasibility count for a new cohort question | minutes, self-service, no ticket | Cohort Builder usage; data-management ticket volume |
| 2 | Cohort reproducibility | every analysis cohort locked with criteria + membership | `Cohort.status = LOCKED` with `criteria_json` |
| 3 | Biomarker review traceability | 100 % of released results have a recorded decision | `BiomarkerReview` per `BiomarkerMeasurement` |
| 4 | Consent compliance | 0 enrolled participants used without valid consent | record rule `ENROLLED_WITHOUT_VALID_CONSENT` open issues |
| 5 | Data quality | no build-blocking expectation failing on production; CRITICAL issues resolved within 2 days | Data Health; `DataQualityIssue` SLA |
| 6 | Access control | no direct identifiers outside the restricted layer | markings on curated/ontology; e2e test `test_no_mrn_reaches_curated_or_ontology` |
| 7 | Adoption | weekly active use by every domain team | platform usage metrics |
