# Access control & markings

TrialLens combines three layers of access control:

1. **Markings (mandatory)** — `markings.yaml`. A user needs *every* marking on a resource.
   Markings travel with lineage, so a dataset derived from identifying data stays
   restricted until a reviewed transform removes the identifying content.
2. **Project roles (discretionary)** — Viewer / Editor / Owner on the TrialLens projects
   (`raw`, `clean`, `curated`, `ontology`, `apps`). Engineers edit code; scientists and
   clinicians only view curated data and use the Workshop apps.
3. **Action submission criteria** — `ontology/action_types.yaml`. Even with object access,
   only reviewers can record biomarker decisions, only data stewards triage issues, and
   only owners can lock cohorts.

## Pseudonymisation boundary

```
raw (MRN, full DOB)  --clean transforms-->  clean (pseudonym + restricted fields)  -->  curated (data-minimised)
   DIRECT_IDENTIFIERS                         DIRECT_IDENTIFIERS                        PSEUDONYMIZED_CLINICAL
```

* Pseudonym: `TL-P-` + first 64 bits of `SHA-256(salt | normalised MRN)`.
* The salt is a single-row dataset at `/TrialLens/secure/pseudonymization_key`, readable
  by the pseudonymisation service user and the DPO group only.
* The curated layer drops full birth date (→ birth year, age band), full postal code
  (→ 2-digit region) and ethnicity. Removing the `DIRECT_IDENTIFIERS` marking at that
  step requires DPO approval (`propagation` in `markings.yaml`).

## Genetic data

`TRIALLENS_GENETIC` is an Art. 9 special category. Genetics-derived *features* used in the
cohort builder (`apoe_e4_carrier`) are only populated from omics samples that passed QC,
and the `consent_genetics` flag on Patient lets the cohort builder exclude participants
without an active genetics consent (see `CONSENT` criteria in the cohort functions).

## Audit

* Every action submission (who, when, parameters, edits) is kept in the action log.
* Dataset reads/exports are covered by the platform audit log, exported daily to the
  DPO's audit project.
* Locked cohorts record criteria and membership at lock time, so any analysis can be
  traced back to the exact patient set and the build of `cohort_features` it came from.
