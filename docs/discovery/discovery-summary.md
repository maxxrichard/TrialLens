# Discovery summary

Four discovery workshops were run with the domain teams that own or consume the data:
**clinical research** (memory clinic physicians, study nurses), **biomarker laboratory**,
**neuroimaging & genomics cores** and **study operations / data management**.

## Problems heard

| Team | Today | Pain |
|---|---|---|
| Clinical research | Cohort questions go to data management as tickets | Days to weeks per feasibility count; criteria re-implemented each time |
| Biomarker lab | Run results reviewed in spreadsheets | No link from a result to the patient's previous values; decisions not traceable |
| Imaging & genomics | Derived measures and manifests on shared drives | Duplicate processing runs; unclear which pipeline version is current |
| Study operations | Consent in a separate registry | Data used without checking current consent scope; manual reconciliation |
| All | Each source has its own IDs and formats | Joining EHR, LIMS, imaging and omics is manual and error-prone |

## Decisions

* One **pseudonymised patient key** across all sources; MRNs stay in the restricted layer.
* A **single feature table** (`cohort_features`) behind the Patient object, so cohort
  criteria are evaluated in one place (Functions) instead of per request.
* **Consent is data**: current consent per scope is part of the patient features and
  gates eligibility and genetic criteria.
* **Review decisions and cohorts are actions**, not spreadsheet edits, so they are audited.
* **Data quality is visible**: expectations block bad builds; record-level issues go to
  a triage queue with owners and SLAs.

See [success-criteria.md](success-criteria.md) for the measurable targets and
[mvp-plan.md](mvp-plan.md) for the six-week MVP scope.
