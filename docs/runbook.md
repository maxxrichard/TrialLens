# Runbook

## A build fails on an expectation

1. Open the failing check in Data Health: the check name is `<dataset>: <expectation>`
   (e.g. `lims_specimens_clean: status_valid`).
2. Find the violating rows: the local engine reports the same check, and the
   `DataQualityCheck` object documents kind, column and severity.
3. Typical causes and fixes:

| Check | Typical cause | Fix |
|---|---|---|
| `*_valid` (in_set) | new code in the source system (e.g. a new LIMS status) | add the mapping in `triallens/logic/<domain>.py`, add a unit test |
| `*_pk` | duplicate extract or ID reuse upstream | confirm with the source owner; adjust de-duplication rule |
| `*_format` (regex) | format change in the extract | extend the parser, never relax the expectation without review |
| `*_plausible` (range) | unit change (e.g. ng/mL instead of pg/mL) | add the unit factor in `reference.UNIT_TO_PG_PER_ML` |

4. Fix on a branch, let CI and the Foundry branch build pass, merge.

## A record-level issue is raised

Issues appear in the Data Quality app, ordered by priority (severity, SLA age, locked
cohort impact). Assign to the owner team of the source (`DataSource.owner_team`), resolve
with a note. CRITICAL issues (`ENROLLED_WITHOUT_VALID_CONSENT`) are escalated to study
operations and the DPO the same day.

## Re-identification request

Only the DPO group can read `/TrialLens/secure/pseudonymization_key`. Requests (e.g. a
clinically relevant incidental finding) follow the study protocol; the DPO recomputes
the pseudonym for the MRN list with `pseudonymize_value` and the action is logged.

## Rotating the salt

Rotation changes every pseudonym. Rebuild all clean/curated/ontology datasets on a
branch, migrate writeback objects (`Cohort`, `CohortMembership`, `BiomarkerReview`) with
an old→new mapping produced inside the restricted project, then promote.
